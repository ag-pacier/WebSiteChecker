# WebSiteChecker
Docker container and Python script to check a website for open ports, a valid certificate and a proper header

## Usage
Get the docker latest docker image by running
```
docker pull dietolead/websitechecker:1.0
```
Grab your API keys for Mailjet by logging into your Mailjet account, clicking on your profile on the top right, then clicking Account Settings.
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

Save the ENV file then run the container:
```
docker run --env-file <location>.env -d dietolead/websitechecker:1.0
```

The container will check all ports you list, the certificate tied to the website and the home page to see if it comes up every 60 seconds. If it encounters an error, it will e-mail the WEB_ADMIN_EMAILS every 30 seconds with the details of what it finds until resolved (or until Mailjet cuts you off).
