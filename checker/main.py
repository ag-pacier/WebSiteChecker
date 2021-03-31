#! python3
# Monitor a given website to make sure everything is kosher

from os import getenv
from socket import socket, AF_INET, SOCK_STREAM
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
web_ports = getenv("WEBSITE_PORTS", default=443)

#Logging setup
if str(getenv("DEBUG")).upper() == "TRUE":
    log_location = r'/log/debug.log'
else:
    log_location = r'/dev/null'

logger = logging.getLogger('WebSiteChecker')

def get_host_ip(url):
    '''Take URL and get its IP using DNSPYTHON.
        Returns IP as STR'''
    result = dns.resolver.resolve(url, 'A')
    return str(result[0])


def error_state(url, error_msg):
    '''Email failure to the webmins
        Tries Mailjet then AWS'''
    if len(mj_api) > 1:
        mailjet_email(url, error_msg)
    elif len(aws_api) > 1:
        aws_email(url, error_msg)
    else:
        raise ValueError("No api keys present! Unable to send e-mail.")


def aws_email(url, error_msg):
    '''Utilize AWS to email failure to the webmins'''
    sender= f"Webmonitor <webmonitor@technicallythoughts.com>"
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
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])


def mailjet_email(url, error_msg):
    '''Utilize mailjet to email failure to the webmins'''
    mailjet = Client(auth=(mj_api, mj_secret))
    data = {
        'Messages': [
            {
                "From": {
                    "Email": "webmonitor@technicallythoughts.com",
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
    result = mailjet.send.create(data=data)
    print(result.status_code)
    print(result.json())


def check_ports(url, *argv):
    '''Go through the ports to check if they are open
        Returns a list of closed ports'''
    failed = []
    ports = []
    #Purge any args that can't be ints
    for arg in argv:
        try:
            int(arg)
        except ValueError:
            continue
        ports.append(arg)
    #Go through each port
    #If they don't respond in 5 seconds, they are considered closed
    for port in ports:
        a_socket = socket(AF_INET, SOCK_STREAM)
        a_socket.settimeout(5)
        location = (url, port)
        result_of_check = a_socket.connect_ex(location)

        if result_of_check == 0:
            print(f"{port} is open")
        else:
            print(f"{port} is not open")
            failed.append(port)

        a_socket.close()
    return failed


def get_status(url):
    '''Checks the header of the given website and returns the status code
        returns the status code as an INT or a big error'''
    #If we forgot HTTPS or HTTP for the schema, add it
    if (url.startswith('http') == False):
        url = "https://" + url
    request_response = head(url)
    print(f"Status code returned: {request_response.status_code}")
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
    print(f"Cert is expired: {x509.has_expired()}")
    return x509.has_expired()


def main():
    while True:
        err = False
        error_dict = {}
        site_ip = get_host_ip(website)
        failures = check_ports(site_ip, web_ports)
        #If there are any failures, call it
        if (len(failures) > 0):
            #error_state(website, f"Ports down: {failures}")
            error_dict["Down Ports"] = failures
            err = True
        status = get_status(website)
        #If the status isn't a number, something went crazy
        try:
            status = int(status)
        except ValueError:
            #error_state(website, f"Status came back not okay: {status}")
            error_dict["Bad Status"] = status
            err = True
        #If the status is 400 or over, it needs to be looked at
        if (status >= 400):
            #error_state(website, f"Website returned a status of: {status}")
            error_dict["Status"] = status
            err = True
        if (check_cert(website)):
            error_dict["Certificate Status"] = "Expired"
            err = True
        #If the error state tripped, sleep 30 and try again
        #Otherwise check again in 60 seconds
        if (err):
            error_state(website, error_dict)
            sleep(30)
        else:
            sleep(60)

if __name__ == "__main__":
    main()
