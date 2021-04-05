FROM python:3.8-slim

#Create folder for storing script and requirements
#Then create folder for logging
RUN mkdir -m 0700 /app && mkdir -m 0704 /log

#Copy script and requirements in
COPY [ "./requirements.txt", "./checker/main.py", "/app/" ]

#Install the requirements
RUN [ "pip", "install", "--no-cache-dir", "-r", "/app/requirements.txt"]

#Run the script
CMD [ "python", "/app/main.py" ]