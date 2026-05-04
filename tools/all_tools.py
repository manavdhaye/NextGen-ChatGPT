# tools/all_tools.py
import base64
import os
import json
import time
import mimetypes
import requests
import smtplib
from email.mime.text import MIMEText
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from huggingface_hub import InferenceClient
from langchain_core.messages import HumanMessage


@tool
def calculator(expression: str) -> str:
    """
    Calculates the result of a mathematical expression.
    
    CRITICAL RULES FOR THE LLM: 
    1. The input must be a strictly formatted mathematical equation.
    2. Use standard operators (+, -, *, /). 
    3. Do NOT pass English words like 'add', 'plus', or 'to'. 
    Example Good Input: '25 + 30'
    Example Bad Input: 'add 25 to 30'
    """
    try:
        # Safely evaluate the math string without allowing system commands
        allowed_names = {"__builtins__": None}
        result = eval(expression, allowed_names, {})
        return str(result)
    except Exception as e:
        # If the LLM still messes up, tell it exactly how to fix it so it can try again!
        return f"Tool Error: Invalid syntax. You passed '{expression}'. Please try again using only numbers and math operators."

@tool
def get_stock_price(symbol: str) -> dict:
    """Fetch stock price."""
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    return requests.get(url).json()

@tool
def draft_email_tool(to_email: str, subject: str, body: str) -> str:
    """
    MANDATORY tool for sending emails. Use this FIRST to stage the draft. 
    You MUST use this tool. Do NOT write the draft directly in your chat response.
    """
    # We package the draft into JSON and add a special prefix 
    # so our agent can catch it and save it to the LangGraph state.
    draft = {"to_email": to_email, "subject": subject, "body": body}
    return f"DRAFT_STAGED: {json.dumps(draft)}"

# @tool
# def email_tool(to: str, subject: str, body: str):
#     """Send an email to a recipient directly. Use this tool when the user wants to send an email."""
#     sender_email = os.getenv("GMAIL_SENDER_EMAIL")
#     app_password = os.getenv("GMAIL_APP_PASSWORD")   

#     msg = MIMEText(body)
#     msg["From"] = sender_email
#     msg["To"] = to
#     msg["Subject"] = subject

#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(sender_email, app_password)
#             server.sendmail(sender_email, to, msg.as_string())
#         return f"Email sent successfully to {to}!"
#     except Exception as e:
#         return f"Failed to send email: {str(e)}"

@tool
def send_email_tool(to_email: str, subject: str, body: str) -> str:
    """Use this tool ONLY AFTER the user has explicitly approved the draft."""
    
    # ... [PUT YOUR ACTUAL EMAIL SENDING LOGIC (SMTP/API) HERE] ...
    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    app_password = os.getenv("GMAIL_APP_PASSWORD")   

    msg = MIMEText(body)
    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        return f"Email sent successfully to {to_email}!"
        print(f"--- 📧 EMAIL SENT TO {to_email} ---")
        return "SUCCESS: Email sent successfully."
    except Exception as e:
        return f"Failed to send email: {str(e)}"

@tool
def whatsapp_tool(to: str, message: str):
    """Send a WhatsApp message to a phone number using UltraMsg API."""
    instance_id = os.getenv("ULTRAMSG_INSTANCE_ID")
    token = os.getenv("ULTRAMSG_TOKEN")

    url = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    
    payload = {
        "token": token,
        "to": to,
        "body": message
    }

    response = requests.post(url, data=payload)
    if response.status_code == 200:
        return f"WhatsApp message sent to {to}!"
    else:
        return f"Failed: {response.text}"
    
@tool
def create_image_tool(prompt:str):
    """Generates an image from a text prompt and saves it."""
    print(f"--- 🎨 GENERATING IMAGE: {prompt} ---")

    client = InferenceClient(
        model="stabilityai/stable-diffusion-xl-base-1.0",
        token=os.getenv("IMAGE_CRAETION_HF_TOKEN") 
    )
    print(client)
    try:
        image = client.text_to_image(prompt)
        print("issue ky ahe",image)
        # Create a safe filename without spaces
        os.makedirs("images", exist_ok=True)
        filename = f"gen_{int(time.time())}.png"
        filepath = os.path.join("images", filename)
        image.save(filepath)
        print(filepath)
        return f"IMAGE_PATH:images/{filename}"
    except Exception as e:
        print(e)
        return f"Failed to generate image: {str(e)}"
    

@tool
def analyze_image_tool(image_filename: str, question: str) -> str:
    """
    A powerful visual analyzer. Use this tool when the user asks a question 
    about an image (png, jpg, jpeg) they have uploaded.
    
    Args:
        image_filename: The exact name of the uploaded image file.
        question: What the user wants to know about the image.
    """
    # 1. Securely locate the image in the Flask uploads folder
    upload_dir = os.path.join(os.getcwd(), "uploads")
    image_path = os.path.join(upload_dir, image_filename)

    print("image tool")
    
    if not os.path.exists(image_path):
        return f"Error: I couldn't find '{image_filename}'. Please ensure it is uploaded."
        
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        print(groq_api_key)
        if not groq_api_key:
            return "Error analyzing image: GROQ_API_KEY is not configured."

        # 2. Encode the image
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            
        # 3. Initialize the Official Groq Vision LLM
        vision_llm = ChatGroq(
            model="meta-llama/llama-4-scout-17b-16e-instruct", 
            temperature=0, 
            max_tokens=1024,
            api_key=groq_api_key
        )
        
        prompt_text = f"""You are an expert visual analyzer and OCR engine. 
        1. Read and extract any text visible.
        2. Understand the visual context.
        3. Answer the user's question accurately: {question}"""
        
        # 4. Format for LangChain Multimodal
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
            ]
        )
        
        # 5. Invoke and return
        response = vision_llm.invoke([message])
        return response.content
        
    except Exception as e:
        return f"Error analyzing image: {str(e)}"