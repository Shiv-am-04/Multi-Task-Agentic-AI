import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph,START,END
from typing import Annotated,Literal
from typing_extensions import TypedDict,List,Optional
from langgraph.graph.message import add_messages
from pydantic import BaseModel,Field
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from langchain_community.utilities import WikipediaAPIWrapper,SerpAPIWrapper
from langchain_community.tools import WikipediaQueryRun
from langchain.agents import Tool
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import mimetypes
from email.mime.multipart import MIMEMultipart
from email import encoders
import base64
from datetime import datetime,timedelta
from groq import Groq
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate


load_dotenv()

groq_api_key = os.getenv('GROQ_API_KEY')
password = os.getenv('PASSWORD')
tavily_api_key = os.getenv('TAVILY_API_KEY')
serpapi_api_key = os.getenv('SERPAPI_API_KEY')

"""***LLM***"""

from langchain_groq import ChatGroq

llm = ChatGroq(model='llama-3.3-70b-versatile',api_key=groq_api_key)


"""***WEB TOOLS***"""

wiki_wrapper = WikipediaAPIWrapper(top_k_results=1)
wiki_tool = WikipediaQueryRun(api_wrapper=wiki_wrapper)

api_wrapper = SerpAPIWrapper(serpapi_api_key = serpapi_api_key)

tools = [
    Tool(
        name="Search",
        func=api_wrapper.run,
        description="Search for anything on the web"
    ),
]

"""***Google API Authentication***"""

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def authenticate_user_for_calender():
    creds = None

    if os.path.exists('calendar_token.pickle'):
        with open('calendar_token.pickle','rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                r'D:\UDEMY\GenAI\Langchain\AI Agent Hackathon\calendar_credentials.json',
                scopes=SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open('calendar_token.pikle','wb') as token:
            pickle.dump(creds,token)

    return creds

# Gmail API

def authenticate_user_for_gmail():
    creds = None

    if os.path.exists('gmail_token.pickle'):
        with open('gmail_token.pickle','rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                r'D:\UDEMY\GenAI\Langchain\AI Agent Hackathon\gmail_credentials.json',
                scopes=["https://www.googleapis.com/auth/gmail.send","https://www.googleapis.com/auth/gmail.modify"]
            )
            creds = flow.run_local_server(port=0)

        with open('gmail_token.pikle','wb') as token:
            pickle.dump(creds,token)

    return creds

"""***Creating Workflow and Integrating Functionality***"""

class State(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: question
        messages: list of messages
    """
    question : List
    messages : List[str]
    storage : Optional[list]
    file : Optional[list]

workflow = StateGraph(State)

"""*Tool*"""

def tool_call(state:State):
    question = state['question'][-1]

    return {'messages':tools[0].invoke(question),'question':question}

##################################
workflow.add_node('Web',tool_call)
##################################

"""*Authentication*"""

def gmail_authentication(state:State):
    question = state['question'][-1]

    credentials = authenticate_user_for_gmail()

    return {'messages':credentials,'question':question}

def calender_authentication(state:State):
    question = state['question'][-1]

    credentials = authenticate_user_for_calender()

    return {'messages':credentials,'question':question}

##########################################################
workflow.add_node('Authenticator_1',gmail_authentication)

workflow.add_node('Authenticator_2',calender_authentication)
###########################################################

"""*Email Sender*"""

class Email(BaseModel):
    sender : str = Field(description='the email of sender')
    receiver : str = Field(description='the email of receiver')
    subject : str = Field(description='the subject of the mail')
    message : str = Field(description='the message to be send in the mail')
    attachment : str = Field(description='the path of the attachment i.e., any file like pdf,audio,image etc.')

email_prompt = ChatPromptTemplate.from_template(
    '''
    If there is any path to the attachment in the {query} then make sure to replace the double backslash or single backslah with the forward slash.
    If there is no path to the attachment then give empty string.
    '''
)

email_llm = llm.with_structured_output(Email)

email_chain = email_prompt|email_llm


def send_mail(sender_mail,receiver_mail,message,subject,cred,attachment=None):
    mail_service = build('gmail','v1',credentials=cred)

    msg = MIMEMultipart()

    msg['To'] = receiver_mail
    msg['From'] = sender_mail
    msg['Subject'] = subject

    body = msg.attach(MIMEText(message))

    if attachment is not None:
        mime_type, _ = mimetypes.guess_type(attachment)

        if mime_type is None:
            mime_type = 'application/octet-stream'

        main_type, sub_type = mime_type.split('/', 1)

        part = MIMEBase(main_type,sub_type)

        with open(attachment,'rb') as file:
            content = file.read()

        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename = {attachment.split('/')[-1]}")
        msg.attach(part)

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    body = {'raw':raw_message}

    message = mail_service.users().messages().send(userId='me',body=body).execute()
    print(f"Email sent successfully! Message ID: {message['id']}")

def mail_sender(state:State):
    question = state['question'][-1]

    credential = state['messages']

    mail = email_chain.invoke(question)

    file = None

    if mail.attachment != '':
        file = mail.attachment

    send_mail(mail.sender,mail.receiver,mail.message,subject=mail.subject,cred=credential,attachment=file)

    return {'messages':mail.message,'question':question}

############################################
workflow.add_node('Mail Sender',mail_sender)
############################################

"""*Email labeling and Removing Labels*"""

def fetch_emails(credentials,query=''):
    service = build('gmail','v1',credentials=credentials)

    # fetching all the unread messages from the user's Gmail account. Any emails that have been read will not be included in this list.
    results = service.users().messages().list(userId='me',q=query).execute()
    message = results.get('messages',[])

    email_list = []
    for msg in message:
        msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
        snippet = msg_data.get("snippet", "")           # It's a small portion of the email's body text, often used to give a quick summary of what the email is about without displaying the entire content.
        headers = msg_data.get("payload", {}).get("headers", [])         # The payload contains the core content of the message, including the headers and body. It essentially represents the entire structure of the email
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")

        email_list.append({
            "id": msg["id"],
            "subject": subject,
            "sender": sender,
            "snippet": snippet,
        })

    return email_list,service

def create_and_apply_labels(label_name,service):
    existing_labels = service.users().labels().list(userId='me').execute()

    label_id = None

    for label in existing_labels.get('labels',[]):
        if label['name'].lower() == label_name.lower():
            label_id = label['id']
            break

    if not label_id:
        label = {
            'name':label_name,
            'labelListVisibility':'labelShow',
            'messageListVisibility':'show'
        }

        labels = service.users().labels().create(userId='me',body=label).execute()

        label_id = labels['id']

    body = {'addLabelIds':[label_id]}

    return body,service


class Criteria(BaseModel):
    criteria : str = Field(description="criteria 'sender' or 'subject' based on which labels are created")

criteria_llm = llm.with_structured_output(Criteria)


def sort_mails(state:State):
    question = state['question'][-1]

    credentials = state['messages']

    criteria = criteria_llm.invoke(question)

    emails,service = fetch_emails(credentials=credentials)

    for email in emails:
        label_name = email[criteria.lower()]

        body,service = create_and_apply_labels(label_name,service)

        service.users().messages().modify(userId='me',id=email['id'],body=body).execute()

    return {'messages':'successfull','question':question,'storage':{'emails':emails,'service':service,'criteria':criteria.lower()}}


def delete_labels(label_name,service):
    existing_labels = service.users().labels().list(userId='me').execute().get('labels',[])

    label_id = None

    for labels in existing_labels:
        if label_name.lower() == labels['name'].lower():
            service.users().labels().delete(userId='me',id=labels['id']).execute()
            label_id = labels['id']
            print(f"label ID {label_id} removed successfully")
            break

def remove_labels(state:State):
    question = state['question'][-1]
    credentials = state['messages']

    info = state['storage'][-1]
    emails = info.get('emails')

    criteria = info.get('criteria')

    for email in emails:
        label_name = email[criteria]
        delete_labels(label_name,info.get('service'))

    return {'messages':credentials,'question':question}

#########################################
workflow.add_node('Sort Mail',sort_mails)
workflow.add_node('Remove',remove_labels)
#########################################

class Remove(BaseModel):
    binary : str = Field(description=" 'y' to remove the labels or 'n' for not to remove the labels")

remove_llm = llm.with_structured_output(Remove)

def remove_or_not(state:State):
    question = state['question'][-1]

    query = remove_llm.invoke(question)

    if query == 'y':
        return 'remove_labels'
    else:
        return END

###########################################################
workflow.add_conditional_edges('Sort Mail',
                               remove_or_not,
                               {
                                   'remove_labels':'Remove',
                                   END:END
                               }
                               )
############################################################

"""*Scheduling Meeting*"""

class Meeting(BaseModel):
    start : datetime = Field(description='the date and time to start and join the meeting')
    participants : list = Field(description='list of emails of few peoples among participants')

meeting_llm = llm.with_structured_output(Meeting)

meeting_llm.invoke('schedule meeting on 26 January 2025 at 18:00 pm,some participants are shivam@kl.com and hello@gmail.com')

def schedule_meetings(meeting_datetime,participants_emails,cred):

    # build() Construct a Resource for interacting with an API.
    calendar_service = build('calendar','v3',credentials=cred)

    event = {
        'summary':'Google Meet Meeting',
        'description':'any',
        'start':{
            'dateTime':meeting_datetime.isoformat(),
            'timeZone':'UTC'
        },
        'end':{
            'dateTime':(meeting_datetime+timedelta(hours=1,minutes=0,seconds=0)).isoformat(),
            'timeZone':'UTC'
        },
        'attendees':[{'email':mail} for mail in participants_emails],
        'conferenceData': {
            'createRequest': {
                'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                'requestId': '121'  # Unique identifier
            }
        }
    }

    # inserting event and integrating with meet
    event = calendar_service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1
    ).execute()

    meet_link = event['hangoutLink']

    print(f"Meeting created successfully! Google Meet Link: {meet_link}")

    return meet_link

def schedule_meeting(state:State):
    question = state['question'][-1]

    credential = state['messages']

    meeting = meeting_llm.invoke(question)

    meet_link = schedule_meetings(meeting.start,meeting.participants,credential)

    return {'messages':f"meeting link : {meet_link}",'question':question}

#############################################
workflow.add_node('Meeting',schedule_meeting)
#############################################

"""***meeting summarizer***"""

class File(BaseModel):
    file_path : str = Field(description='the path of the uploaded file')

transcription_llm = llm.with_structured_output(File)

prompt = ChatPromptTemplate.from_template(
    '''convert the double backslash of the path in the {query} to the forward slash. 
    Make sure only to provide the path nothing extra than that.'''
)

transcription_chain = prompt|transcription_llm

def transcription_of_audio(file_path):
    client = Groq()

    prompt = '''
    You are a highly skilled transcriptionist with over 15 years of experience in converting audio recordings into accurate, well-structured,
    and easy-to-read dialogue formats. Your expertise lies in capturing the nuances of conversations, including tone, pauses, and key points,
    while maintaining clarity and coherence.
    Here's an example of how you format the transcription :
    [Speaker 1] : "Let's start by reviewing the project timeline. Does everyone have the updated document?"
    [Speaker 2] : "Yes, I've gone through it. I think we need to adjust the deadlines for phase two."
    [Speaker 1] : "Agreed. Let's discuss that in detail after we cover the budget updates."
    '''
    txt = []

    with open(file_path, "rb") as audio_file:
        content = audio_file.read()

    transcription = client.audio.transcriptions.create(
        file=(file_path,content),
        model='whisper-large-v3-turbo',
        prompt=prompt,
        response_format='json',
        language='en',
        temperature=0.2
    )

    txt.append(transcription.text)

    return txt

def transcriber(state:State):
    question = state['question'][-1]

    print(question)

    file_path = transcription_chain.invoke({'query':question})

    print(file_path)

    response = transcription_of_audio(file_path.file_path)

    return {'messages':Document(page_content=response[0]),'question':question}

##############################################
workflow.add_node('Extract Audio',transcriber)
##############################################

from typing import Literal

class Route(BaseModel):
    '''
    This class is likely used to determine where to route a user's question
    '''
    datasource :Literal['gmail_authentication','calender_authentication','transcribe_audio','web_search'] = Field(
        ...,
        description = "Given user's question choose to route it to gmail authentication or calender authentication or transcribing audio or web search"
    )

route = llm.with_structured_output(Route)


def authentication_router(state:State):
    source = route.invoke(state['question'][-1])

    if source.datasource == 'gmail_authentication':
        return 'authenticate_mail'
    elif source.datasource == 'calender_authentication':
        return 'authenticate_calender'
    elif source.datasource == 'transcribe_audio':
        return 'transcriber'
    else:
        return 'web_search'

workflow.add_conditional_edges(
    START,
    authentication_router,
    {
        'authenticate_calender':'Authenticator_2',
        'authenticate_mail':'Authenticator_1',
        'transcriber':'Extract Audio',
        'web_search':'Web'
    }
)

class SendSort(BaseModel):
    option : str = Field(description='send if user want to send the mail or sort if user want to sort/apply labels')

sendOrsort = llm.with_structured_output(SendSort)

def send_or_sort(state:State):
    q = sendOrsort.invoke(state['question'][-1])

    if q.option == 'send':
        return 'mail_sender'
    else:
        return 'apply_labels'

workflow.add_conditional_edges(
    'Authenticator_1',
    send_or_sort,
    {
        'mail_sender':'Mail Sender',
        'apply_labels':'Sort Mail'
    })
workflow.add_edge('Authenticator_2','Meeting')

workflow.add_edge('Web',END)
workflow.add_edge('Mail Sender',END)
workflow.add_edge('Meeting',END)
workflow.add_edge('Extract Audio',END)

graph = workflow.compile()

__all__ = ['workflow','graph','transcription_of_audio']
