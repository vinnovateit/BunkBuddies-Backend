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
            subject="BunkBuddies - Room Request Digest",
            context={
                "admin_name": "ADMIN",
                "request_count": 2,
                "requests": [
                    {
                        "sender_name": "ABC",
                        "sender_reg": "25BCE2425",
                        "group_name": "XYZ"
                    },
                    {
                        "sender_name": "PQR",
                        "sender_reg": "25CSE1111",
                        "group_name": "XYZ"
                    },
                ],
            }
        )
        print("--- All tests completed successfully! ---")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
