# Getting the broker's report via a direct link

To get the broker's report WITHOUT authorization in the system, you will require an API key

#### Links to the report receiving options:

| File format | Report link
|---|---|---|---|
|
|
|
|

To get the report with a specific start date, you need to add the date_start parameter  ...&date_start=2020-01-01,  where it is 2020-01-01 - this is the start date for creating the report in the format YYYY-MM-DD

To get the report with a specific end date, you need to add the date_end parameter  ...&date_end=2020-02-01,  where 2020-02-01 is the report generation end date in the YYYY-MM-DD format

To get the report WITHOUT authorization, you need to generate an API key in the profile and add it to the end of the link as a parameter  ...&api_key=API_KEY,  where it is API_KEY - this is your key obtained from the profile ;

you also need to specify the login of a client for whom you want to get the report and add it to the end of the link as a parameter  ...&auth_login=LOGIN,  where it is LOGIN - this is your login

#### Generator of links to receive reports
