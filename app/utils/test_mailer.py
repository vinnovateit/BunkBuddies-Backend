import asyncio
import sys
import os

# This ensures Python can see the 'app' folder
sys.path.append(os.getcwd())

from app.utils.mailer import mailer 

async def main():
    print("--- Starting Mailer Test ---")
    
    try:
        # Test Email 1: Request Accepted
        print("Sending Request Accepted email...")
        await mailer(
            template_path="app/templates/emails/request_accepted.html",
            email_to="shreya.verma2025@vitstudent.ac.in",
            subject="BunkBuddies - Request Accepted",
            context={
                "student_name": "PQR",
                "group_name": "XYZ"
            }
        )

        # Test Email 2: Request Received
        print("Sending Request Received email...")
        await mailer(
            template_path="app/templates/emails/request_received.html",
            email_to="shreya.verma2025@vitstudent.ac.in",
            subject="BunkBuddies - Request Received",
            context={
                "admin_name": "ADMIN", 
                "group_name": "XYZ",
                "sender_name": "ABC",
                "sender_reg": "25BCE2425",
                "sender_mob": "XXXXX XXXXX",
                "sender_mail": "test@vitstudent.ac.in"
            }
        )
        print("--- All tests completed successfully! ---")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())