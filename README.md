# WebSiteChecker
Docker container and Python script to check a website for open ports, a valid certificate and a proper header

## Usage
Get the docker latest docker image by running
```
docker pull dietolead/websitechecker:latest
```
Grab your API keys:

### For Mailjet:
Log into your Mailjet account, clicking on your profile on the top right, then clicking Account Settings.
Under REST API, click on Master API Key & Sub API key management.
Leave the window up so you can appropriate populate your ENV file.

In a folder of your choosing, create an ENV file and populate it based on the sample ENV
```
WEBSITE_ADDRESS=<website you want to monitor>
MJ_APIKEY_PUBLIC=<Master API key from Mailjet>
MJ_APIKEY_PRIVATE=<Secret Key from Mailjet>
WEB_ADMIN_EMAILS=<email addresses of folks who need to know if something is wrong separated by ;>
WEBSITE_PORTS=<ports that should be open>
```
### For AWS:

Login to your AWS console as an administrative user. Create a user with full access to the SES API and no console access. Generate Access Keys and save the CSV in a secure location.

Ensure your domain is added and verified in the SES console. Configure to be able to send email to your addresses that will be listed in the WEB_ADMIN_EMAILS entry in the ENV file you will create. If sending outside your domain, ensure you are not in the sandbox mode in SES before beginning monitoring.

In a folder of your choosing, create an ENV file and populate it based on the sample ENV
```
WEBSITE_ADDRESS=<website you want to monitor>
AWS_ACCESS_KEY_ID=<first entry in saved CSV>
AWS_SECRET_ACCESS_KEY=<Second entry in saved CSV>
AWS_REGION=<region to e-mail from>
WEB_ADMIN_EMAILS=<email addresses of folks who need to know if something is wrong separated by ;>
WEBSITE_PORTS=<ports that should be open>
```

Save the ENV file then run the container:
```
docker run --env-file <location>.env -d dietolead/websitechecker:latest
```

The container will check all ports you list, the certificate tied to the website and the home page to see if it comes up every 60 seconds. If it encounters an error, it will e-mail the WEB_ADMIN_EMAILS every 30 seconds with the details of what it finds until resolved.

## Logging
Logging has been refined to now use the logging package instead of print statements.

By default, the level is set to INFO which will provide you with basic feedback on what's going on. If you add the following to your ENV file:
```
DEBUG=true
```
then verbose, debug logging will be enabled and be put out to the file /log/debug.log for which you will need to make a bindmount. So your new run command would be:
```
docker run --env-file <location>.env -v <location you want your log>:/log -d dietolead/websitechecker:latest
```

### Notes regarding logging
Uninclusive valid debug options recognized in Python:
```
DEBUG=TRUE
DEBUG=true
DEBUG=tRuE
DEBUG=tRUE
DEBUG=True
```
uninclusive invalid debug options:
```
DEBUG=false
DEBUG='true'
DEBUG="True"
```

Although passwords are not saved in the log, the API keys are so please keep those logs secure. Additionally, debug logging adds a line for just about every function so please do not run it in production as it will fill up rapidly.