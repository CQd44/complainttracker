'''
This is a way to track complaints made, the call center management's response to said complaints, and whether or not
those complaints are valid (in the sense that they actually pertain to actions taken by our staff here).

This runs on port 8300


Written by Clay Young
william.youngiv@dhr-rgv.com
Extension x21965

'''

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import psycopg2
import smtplib
import toml
import csv
from time import gmtime, strftime
from pydantic import BaseModel


CONFIG = toml.load("./config.toml") #load variables from toml file
app = FastAPI()
templates = Jinja2Templates(directory="templates") #loads HTML files from this directory
SERVER: str = CONFIG['comms']['server']
PORT: int = CONFIG['comms']['port']
FROM: str = CONFIG['comms']['from']
TO: list[str] = CONFIG['comms']['emails'] 

class TicketUpdate(BaseModel):
    ticket_id: str | int
    complaint: str
    response: str
    
#send email
def send_email(complaint, response, new_id, validity):
    msg_text = f"""\
Subject: Complaint Form Submission

Complaint Received: {complaint}

Call Center Response:  {response}

Complaint ID: {new_id}
"""

    with smtplib.SMTP(SERVER, PORT, timeout = 20) as server:
        server.ehlo()
        server.sendmail(FROM, TO, msg_text)
        server.quit()
        print("Email sent!")

# Set up postgresql database
def init_db():
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS complaints 
                (id SERIAL PRIMARY KEY, 
                complaint TEXT,
                response TEXT,
                validity BOOL,
                EntryDate TIMESTAMP DEFAULT Now())'''
            )
    cur.close()
    con.commit()

# Home page with the form
@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

# Handle form submission
@app.post("/submit")
async def submit_form(request: Request, complaint: str = Form(...), response: str = Form(...), validity: bool | str | None = Form(...)):
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = "INSERT INTO complaints (complaint, response, validity) VALUES (%s, %s, %s);"
    if validity == 'Unknown':
        validity_2 = None
    DATA = (complaint.strip(), response.strip(), validity_2) # type: ignore
    cur.execute(SQL, DATA)  
    cur.execute("SELECT id FROM complaints ORDER BY id DESC LIMIT 1")
    new_id: int = cur.fetchone()[0] # type: ignore
    cur.close()
    con.commit()
    send_email(complaint, response, new_id, validity)
    return RedirectResponse(url=f"/thank-you?id={new_id}", status_code=303)

# Update Complaint
@app.post("/update_complaint")
async def update_complaint(request: Request, update_complaint: str = Form(...), id: int = Form(...)):
    if update_complaint == "" or update_complaint == None: #catches if nothing was entered
        return HTMLResponse(content="<h1>No information entered to update complaint.</h1><a href = '/'>Go back</a>")
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = "SELECT complaint FROM complaints WHERE id = %s;"
    DATA = (id, )
    cur.execute(SQL, DATA)  
    current_complaint: str = cur.fetchone()[0]  # type: ignore
    print(current_complaint)
    current_complaint = current_complaint + f'\n\nUPDATED {strftime("%Y-%m-%d %H:%M:%S", gmtime())}\n\n{update_complaint}'
    print(current_complaint)
    SQL = "UPDATE complaints SET complaint = %s WHERE id = %s;"
    DATA = (current_complaint, id)
    cur.execute(SQL, DATA)
    cur.close()
    con.commit()
    return HTMLResponse(content=f"<h1>Complaint updated.</h1><a href = '/view?id={id}'>Go back</a>")


# Update Action Taken
@app.post("/update_response")
async def update_response(request: Request, update_response: str = Form(...), id: int = Form(...)):
    if update_response == "" or update_response == None: #catches if nothing was entered
        return HTMLResponse(content="<h1>No information entered to update action taken.</h1><a href = '/'>Go back</a>")
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = "SELECT response FROM complaints WHERE id = %s;"
    DATA = (id, )
    cur.execute(SQL, DATA)  
    current_response: str = cur.fetchone()[0]  # type: ignore
    current_response = current_response + f'\n\nUPDATED {strftime("%Y-%m-%d %H:%M:%S", gmtime())}\n\n{update_response}'
    SQL = "UPDATE complaints SET complaint = %s WHERE id = %s;"
    DATA = (current_response, id)
    cur.execute(SQL, DATA)
    cur.close()
    con.commit()
    return HTMLResponse(content="<h1>Action taken updated.</h1><a href = '/'>Go back</a>")


# Update Both Complaint and Action Taken
@app.post("/update_both")
async def update_both(ticket: TicketUpdate):    
    if ticket.complaint == "" or ticket.complaint == None: #catches if nothing was entered
        return HTMLResponse(content="<h1>No information entered to update complaint.</h1><a href = '/'>Go back</a>")
    if ticket.response == "" or ticket.response == None: #catches if nothing was entered
        return HTMLResponse(content="<h1>No information entered to update action taken.</h1><a href = '/'>Go back</a>")
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = "SELECT complaint FROM complaints WHERE id = %s;"
    DATA = (ticket.ticket_id, )
    cur.execute(SQL, DATA)  
    current_complaint: str = cur.fetchone()[0]  # type: ignore
    
    current_complaint = current_complaint + f"""
    UPDATED {strftime("%Y-%m-%d", gmtime())}:
    {ticket.complaint}"""
    
    SQL = "UPDATE complaints SET complaint = %s WHERE id = %s;"
    DATA = (current_complaint, ticket.ticket_id)
    cur.execute(SQL, DATA)
    SQL = "SELECT response FROM complaints WHERE id = %s;"
    DATA = (ticket.ticket_id, )
    cur.execute(SQL, DATA)  
    current_response: str = cur.fetchone()[0]  # type: ignore
    print(current_response)

    current_response = current_response + f"""      
    UPDATED {strftime("%Y-%m-%d", gmtime())}:
    {ticket.response}"""
    
    SQL = "UPDATE complaints SET response = %s WHERE id = %s;"
    DATA = (current_response, ticket.ticket_id)
    cur.execute(SQL, DATA)
    cur.close()
    con.commit()
    return HTMLResponse(content=f"<h1>Complaint updated.</h1><a href = '/view?id={ticket.ticket_id}'>Go back</a>")

# Thank-you page
@app.get("/thank-you", response_class=HTMLResponse)
async def thank_you(request: Request, id: int):
    return templates.TemplateResponse("thank_you.html", {"request": request, "id" : id})

#Page to let users check on their ticket if they search by ID
@app.get("/view", response_class = HTMLResponse)
async def view_ticket(request: Request, id: int):
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = 'SELECT * FROM complaints WHERE id = (%s);'
    DATA = id
    cur.execute(SQL, (DATA,))
    
    result = cur.fetchone()
    cur.close()

    if result:
        ticket_data = {
                       "id" : result[0], 
                       "complaint" : result[1].strip(), 
                       "response" : result[2].strip(), 
                       "entrydate" : result[-1], 
                       "validity" : result[3]
                       }
        return templates.TemplateResponse("view_row.html", {"request" : request, "ticket_data" : ticket_data})
    else:
        return HTMLResponse(content="<h1>Complaint not found.</h1><a href = '/'>Go back</a>")

@app.get("/viewlog", response_class=HTMLResponse)
async def viewdb(request: Request):
    return templates.TemplateResponse("viewdb.html", {"request": request})

@app.get("/fetch", response_class=HTMLResponse)
async def getdb():
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = "SELECT * FROM complaints ORDER BY id ASC;"
    cur.execute(SQL)

    results = []
    loc_results = cur.fetchall()

    for row in loc_results:
        results.append(row)
    SQL = "SELECT column_name FROM information_schema.columns WHERE table_name = 'complaints';"
    cur.execute(SQL)
    result_rows = cur.fetchall()
    columns = []
    for row in result_rows:
        columns.append(row[0])
    cur.close()
    con.close()

    result_dict = {}
    result_list = []

    for i in range(len(results)):
        result_dict[i + 1] = {columns[0] : results[i][0], columns[-2] : str(results[i][1]), columns[-1] : results[i][2], columns[1] : results[i][3], columns[2] : str(results[i][-1])}

    for i in range(len(results)):
        result_list.append(result_dict[i+1])

    return JSONResponse(content=result_list, status_code=200)

@app.get("/download", response_class=HTMLResponse)
async def download_db(request: Request):
    con = psycopg2.connect(f'dbname = {CONFIG['credentials']['dbname']} user = {CONFIG['credentials']['username']} password = {CONFIG['credentials']['password']}')
    cur = con.cursor()
    SQL = "SELECT * FROM complaints ORDER BY id ASC;"
    cur.execute(SQL)

    results = []
    loc_results = cur.fetchall()

    for row in loc_results:
        results.append(row)
    SQL = "SELECT column_name FROM information_schema.columns WHERE table_name = 'complaints';"
    cur.execute(SQL)
    result_rows = cur.fetchall()
    columns = []
    for row in result_rows:
        columns.append(row[0])
    actual_columns: list = []
    actual_columns.append(columns[0])
    actual_columns.append(columns[-2])
    actual_columns.append(columns[-1])
    actual_columns.append(columns[1])
    actual_columns.append(columns[2])
    cur.close()
    con.close()

    with open('log.csv', 'w', newline = '') as output:
        writer = csv.writer(output)
        writer.writerow(actual_columns)
        writer.writerows(results)

    return FileResponse(path='.\log.csv', status_code=200, media_type="csv", filename="log.csv") # type: ignore

# Initialize the database when the app starts
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
    except Exception as e:
        print(e)
