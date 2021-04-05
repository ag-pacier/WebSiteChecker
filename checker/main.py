#! python3
# Monitor a given website to make sure everything is kosher

from os import getenv, devnull
from socket import socket, AF_INET, SOCK_STREAM, error
from requests import head
from time import sleep
from mailjet_rest import Client
from botocore.exceptions import ClientError
import OpenSSL, ssl, dns.resolver, boto3, logging

website = str(getenv("WEBSITE_ADDRESS", default='massport.com'))
mj_api = str(getenv("MJ_APIKEY_PUBLIC"))
mj_secret = str(getenv("MJ_APIKEY_PRIVATE"))
aws_api = str(getenv("AWS_ACCESS_KEY_ID"))
aws_secret = str(getenv("AWS_SECRET_ACCESS_KEY"))
aws_region = str(getenv("AWS_REGION"))
webmins = str(getenv("WEB_ADMIN_EMAILS"))
email_domain = str(getenv("EMAIL_DOMAIN"))
web_ports = str(getenv("WEBSITE_PORTS", default=443)).split(',')

#Logging setup
logger = logging.getLogger('WebSiteChecker')
if str(getenv("DEBUG")).upper() == "TRUE":
    log_location = r'/log/debug.log'
    logger.setLevel(logging.DEBUG)
else:
    #Use os.devnull to send to null device
    log_location = devnull
    logger.setLevel(logging.WARNING)

file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler(log_location, mode='a')
fh.setLevel(logging.DEBUG)
fh.setFormatter(file_format)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
ch.setFormatter(stream_format)
logger.addHandler(ch)


def get_host_ip(url):
    '''Take URL and get its IP using DNSPYTHON.
        Returns IP as STR'''
    svr_info = dns.resolver.Resolver()
    try:
        result = dns.resolver.resolve(url, 'A')
    except Exception as e:
        logger.debug(f'DNS Server used: {svr_info.nameservers}')
        logger.critical(e)
    logger.debug(f'get_host_ip pulled {result[0]} from {svr_info.nameservers}')
    return str(result[0])


def error_state(url, error_msg):
    '''Email failure to the webmins
        Tries Mailjet then AWS'''
    if len(mj_api) > 4:
        logger.debug(f'Mailjet API picked as length is {len(mj_api)}')
        mailjet_email(url, error_msg)
    elif len(aws_api) > 4:
        logger.debug(f'Mailjet API skipped as length is {mj_api} and AWS API is {len(aws_api)}')
        aws_email(url, error_msg)
    else:
        logger.error('Both APIs are under 1 char.')
        logger.debug(f'Mailjet: {mj_api}')
        logger.debug(f'AWS: {aws_api}')
        raise ValueError("No api keys present! Unable to send e-mail.")


def aws_email(url, error_msg):
    '''Utilize AWS to email failure to the webmins'''
    sender= f"Webmonitor <webmonitor@{email_domain}>"
    subject = f'Error on {url}'
    body_txt = f'An error has occurred for {url} which is returned with: {error_msg}'
    body_html = f'<p>An error has occurred for {url} with the following message:</p>{error_msg}'
    char_set = 'UTF-8'

    # Create a new SES resource and specify a region.
    client = boto3.client('ses', region_name=aws_region)

    try:
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    webmins,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': char_set,
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': char_set,
                        'Data': body_txt,
                    },
                },
                'Subject': {
                    'Charset': char_set,
                    'Data': subject,
                },
            },
            Source=sender,
        )

    # Display an error if something goes wrong.
    except ClientError as e:
        logger.critical(e.response['Error']['Message'])
    except Exception as e:
        logger.critical(e)
    else:
        logger.info("Email sent! Message ID:"),
        logger.info(response['MessageId'])


def mailjet_email(url, error_msg):
    '''Utilize mailjet to email failure to the webmins'''
    try:
        mailjet = Client(auth=(mj_api, mj_secret))
    except Exception as e:
        logger.critical(e)
    data = {
        'Messages': [
            {
                "From": {
                    "Email": f"webmonitor@{email_domain}",
                    "Name": "Webmonitor"
                },
                "To": [
                    {
                        "Email": f"{webmins}",
                        "Name": "Web Admins"
                    }
                ],
                "Subject": f"Error on {url}",
                "TextPart": f"An error has occurred for {url}",
                "HTMLPart": f"The website monitor for {url} has reported there is a problem with the website. <br /> {error_msg}"
            }
        ]
    }
    try:
        result = mailjet.send.create(data=data)
    except Exception as e:
        logger.critical(e)
    logger.info(f'Mailjet returned a code of: {result.status_code}')
    logger.debug(result.json())


def check_ports(url, webports):
    '''Go through the ports to check if they are open
        Returns a list of closed ports'''
    failed = []
    ports = []
    #Purge any args that can't be ints
    for arg in webports:
        try:
            int(arg)
            logger.debug(f'Added {arg} to list of monitored ports')
        except ValueError:
            logger.error(f'Cannot add {arg} to ports list, skipping.')
            continue
        ports.append(int(arg))
        logger.debug(f'Ports being monitored: {ports}')
    #Go through each port
    #If they don't respond in 5 seconds, they are considered closed
    for port in ports:
        a_socket = socket(AF_INET, SOCK_STREAM)
        a_socket.settimeout(5)
        location = (url, port)
        logger.debug(f'Location set to: {location}')
        try:
            result_of_check = a_socket.connect_ex(location)
        except TypeError as e:
            logger.debug(f'Location types: {type(location)} :: URL: {type(location[0])} :: port: {type(location[1])}')
            logger.critical(e)
        except TimeoutError as e:
            logger.debug(f'Socket returned: {e}')
            continue


        if result_of_check == 0:
            logger.info(f"{port} is open")
        else:
            logger.warning(f"{port} is not open")
            failed.append(port)

        a_socket.close()
    logger.debug(f'Returning list of failed ports as: {failed}')
    return failed


def get_status(url):
    '''Checks the header of the given website and returns the status code
        returns the status code as an INT or a big error'''
    #If we forgot HTTPS or HTTP for the schema, add it
    if (url.startswith('http') == False):
        url = "https://" + url
    logger.debug(f'get_status using {url}')
    request_response = head(url)
    logger.info(f"Status code returned: {request_response.status_code}")
    return request_response.status_code


def check_cert(url):
    '''Checks to see if provided url has an expired cert
        Returns a BOOL
        TRUE == certificate has expired
        FALSE == certificate is OK'''
    #Grab the cert from the given URL
    cert = ssl.get_server_certificate((url, 443))
    #Load it so we can check it
    x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
    logger.info(f"Cert is expired: {x509.has_expired()}")
    return x509.has_expired()


def main():
    while True:
        err = False
        error_dict = {}
        logger.debug('Cleared error status for new checks.')
        site_ip = get_host_ip(website)
        failures = check_ports(site_ip, web_ports)
        #If there are any failures, call it
        if (len(failures) > 0):
            error_dict["Down Ports"] = failures
            err = True
        status = get_status(website)
        #If the status isn't a number, something went crazy
        try:
            status = int(status)
        except ValueError:
            logger.warning("Status returned a non-int!")
            error_dict["Bad Status"] = status
            err = True
        #If the status is 400 or over, it needs to be looked at
        if (status >= 400):
            logger.warning("Status is 400 or over, indicating an issue!")
            error_dict["Status"] = status
            err = True
        if (check_cert(website)):
            logger.warning("Certificate is expired!")
            error_dict["Certificate Status"] = "Expired"
            err = True
        #If the error state tripped, sleep 30 and try again
        #Otherwise check again in 60 seconds
        if (err):
            logger.debug(f'Error state tripped with: {error_dict}')
            error_state(website, error_dict)
            sleep(30)
        else:
            logger.debug('Error state not tripped, sleeping for 60 seconds.')
            sleep(60)

if __name__ == "__main__":
    logger.debug('Webchecker starting. Logging captured settings.')
    logger.debug(f'Website: {website}')
    logger.debug(f'APIs: {mj_api} :: {aws_api}')
    if len(aws_region) > 0:
        logger.debug(f'AWS Region: {aws_region}')
    logger.debug(f'Admin emails: {webmins}')
    logger.debug(f'Ports supplied: {web_ports}')
    main()
