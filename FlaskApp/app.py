from fastapi import FastAPI, Request, Form, Depends, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from bson import ObjectId
import os
import json
from datetime import datetime

# Load configuration
with open('config.json', 'r') as c:
    params = json.load(c)["params"]

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# MongoDB connection
client = AsyncIOMotorClient(params['mongo_uri'])
db = client[params['mongo_db_name']]

# Email configuration
# conf = ConnectionConfig(
#     MAIL_USERNAME=params['gmail-user'],
#     MAIL_PASSWORD=params['gmail-password'],
#     MAIL_FROM=params['gmail-user'],
#     MAIL_PORT=465,
#     MAIL_SERVER="smtp.gmail.com",
#     MAIL_FROM_NAME="Your App",
#     MAIL_TLS=False,
#     MAIL_SSL=True,
#     USE_CREDENTIALS=True
# )

# Pydantic models
class Contact(BaseModel):
    name: str
    phone_num: str
    msg: str
    email: str
    date: datetime = datetime.now()

class Post(BaseModel):
    title: str
    slug: str
    content: str
    tagline: str = None
    img_file: str = None
    date: datetime = datetime.now()

# Utility function to parse ObjectId in MongoDB documents
def format_id(document):
    document["_id"] = str(document["_id"])
    return document

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    posts = await db["posts"].find().to_list(length=100)
    posts = [format_id(post) for post in posts]
    return templates.TemplateResponse("index.html", {"request": request, "params": params, "posts": posts})

@app.get("/post/{post_slug}", response_class=HTMLResponse)
async def post_route(request: Request, post_slug: str):
    post = await db["posts"].find_one({"slug": post_slug})
    if post:
        post = format_id(post)
        return templates.TemplateResponse("post.html", {"request": request, "params": params, "post": post})
    raise HTTPException(status_code=404, detail="Post not found")

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request, "params": params})

@app.post("/contact")
async def contact(name: str = Form(...), email: str = Form(...), phone: str = Form(...), message: str = Form(...)):
    entry = Contact(name=name, phone_num=phone, msg=message, email=email)
    await db["contacts"].insert_one(entry.dict())
    message = MessageSchema(
        subject=f"New message from {name}",
        recipients=[params['gmail-user']],
        body=f"{message}\n{phone}",
        subtype="plain"
    )
    # fm = FastMail(conf)
    await fm.send_message(message)
    return {"message": "Message sent"}

@app.post("/uploader")
async def uploader(file: UploadFile = File(...)):
    file_location = os.path.join(params["upload_location"], file.filename)
    with open(file_location, "wb") as f:
        f.write(file.file.read())
    return {"info": f"File '{file.filename}' uploaded successfully"}

# Authentication routes (adjust as per your requirement)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Add authentication logic if needed
    posts = await db["posts"].find().to_list(length=100)
    return templates.TemplateResponse("dashboard.html", {"request": request, "params": params, "posts": posts})

@app.post("/edit/{sno}")
async def edit(sno: str, title: str = Form(...), tline: str = Form(...), slug: str = Form(...), content: str = Form(...), img_file: str = Form(...)):
    post_data = Post(title=title, tagline=tline, slug=slug, content=content, img_file=img_file)
    if sno == '0':
        await db["posts"].insert_one(post_data.dict())
    else:
        await db["posts"].update_one({"_id": ObjectId(sno)}, {"$set": post_data.dict()})
    return RedirectResponse(url=f"/edit/{sno}", status_code=303)

@app.post("/delete/{sno}")
async def delete(sno: str):
    await db["posts"].delete_one({"_id": ObjectId(sno)})
    return RedirectResponse(url="/dashboard", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
