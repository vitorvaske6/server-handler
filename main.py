import subprocess
import smtplib
import os
import sys
import json
from typing import Literal, Union
from redmail import EmailSender
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv  # to use .env
load_dotenv()
jsonArg=None

EMAIL_SEND_REPORT = os.getenv("EMAIL_SEND_REPORT")
PASSWORD_SEND_REPORT = os.getenv("PASSWORD_SEND_REPORT")
EMAIL_LIST = os.getenv("EMAIL_LIST")

class Args:
    def __init__(self, function: str, check_service_status: str, package_manager: str, config_file_path: str, service_name: str, cwd: str):
        self.function = function
        self.check_service_status = check_service_status
        self.package_manager = package_manager
        self.config_file_path = config_file_path
        self.service_name = service_name
        self.cwd = cwd

def send_error(html: str, subject: str, attachment: str):
    """
    Função que realiza o envio do email.

    """

    try:

        email_sender_ = f"{EMAIL_SEND_REPORT}"
        password_ = f"{PASSWORD_SEND_REPORT}"

        email = EmailSender(host="smtp.office365.com", port=587,
                            username=email_sender_, password=password_)

        email.send(
            subject=subject,
            receivers=EMAIL_LIST,
            html=html,
            attachments={
                f'{attachment}': Path(attachment),
            },
        )

    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error = f"Error sending error email: ", err, f" | Traceback: {exc_type} | File: {fname} | Line error: {exc_tb.tb_lineno}"
        print_logs(error, True)


def print_logs(logs, error=False):
    # Create logs directory if it doesn't exist
    os.makedirs('./logs', exist_ok=True)
    
    # Create log file with current date
    log_file = f"./logs/log_print_{datetime.now().strftime('%Y%m%d')}.txt"
    
    # Append logs to file
    with open(log_file, 'a') as f:
        f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {str(logs)}")
    
    if error:
        send_error(
            f"Error while executing {jsonArg.function if jsonArg != None else 'Unknown'} function.\nError: {logs}", 
            f"""Service {jsonArg.service_name if jsonArg != None else 'Unknown'}""",
            log_file
        )
        
    print(logs)

def check_service_status(args: Args) -> Union[Literal["online"], Literal["stopped"], None]:
    try:
        def check_service():
            # Check if service is running using pm2 jlist
            result = subprocess.run(['pm2', 'jlist', '-s'],
                                    capture_output=True, text=True, shell=True)
            
            if result.stdout != '[]' and result.stdout:
                servers_running = json.loads(result.stdout)
                for server in servers_running:
                    if server['name'] == args.service_name:
                        return server['pm2_env']['status']
            return 'offline'
        current_status = check_service()
        if current_status != 'offline': return current_status
        else:
            # result = subprocess.run(['pm2', 'start', os.path.join(args.config_file_path), '--only', args.service_name],
            #                     capture_output=True, text=True, shell=True, encoding='utf-8')
            cmd = f"pm2 start \"{args.config_file_path}\" --only \"{args.service_name}\""
            # result = subprocess.run(cmd, check=True, capture_output=True, text=True, shell=True, encoding='utf-8')
            result = subprocess.run(cmd, capture_output=True, shell=True, check=True, text=True, encoding='utf-8')
            
            current_status = check_service()
            if current_status != 'offline': return 'starting'
            else: return 'stopped-error'
            print('result.stdout: ', result.stdout)
            print('run: ', ['pm2', 'start', os.path.join(args.config_file_path), '--only', args.service_name])
            print('cmd: ', cmd)
        return None
    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error = f"Error checking service status: {str(err)}\n result.stdout: {result.stdout}", f" | Traceback: {exc_type} | File: {fname} | Line error: {exc_tb.tb_lineno}"
        print_logs(error, True)
        return None


def get_pm2_logs(service_name):
    try:
        # Get the latest logs
        result = subprocess.run(['pm2', 'logs', service_name, '--lines', '5000', '--nostream'],
                                capture_output=True, text=True, shell=True)
        return result.stdout
    except Exception as e:
        return f"Error getting logs: {str(e)}"


def send_email(log_file: str, subject: str, html: str):
    """
    Função que realiza o envio do email.

    """

    try:

        email_sender_ = f"{EMAIL_SEND_REPORT}"
        password_ = f"{PASSWORD_SEND_REPORT}"

        email = EmailSender(host="smtp.office365.com", port=587,
                            username=email_sender_, password=password_)

        email.send(
            subject=subject,
            receivers=EMAIL_LIST,
            html=html,
            attachments={
                f'{log_file}': Path(log_file),
            },
        )

    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error = f"Error sending success email. \nError: {str(err)}", f" | Traceback: {exc_type} | File: {fname} | Line error: {exc_tb.tb_lineno}"
        print_logs(error, True)


def check_and_run(args: Args):
    run = check_service_status(args)
    if not run:
        print_logs(f"Service {args.service_name} not found. Exiting...")
    elif run == "starting":
        print_logs(f"Service {args.service_name} is not running. Attempting to start...")
        try:
            # Get logs after restart
            logs = get_pm2_logs(args.service_name)
            # Create logs file attachment
            log_file = f"./logs/pm2_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            with open(log_file, 'w') as f:
                f.write(logs)

            # Send email notification
            send_email(log_file, f"Service {args.service_name} has been registered and started", f"Service {args.service_name} has been registered and started and logs are attached.")

            print_logs(f"Service {args.service_name} has been started and notification sent.")
        except subprocess.CalledProcessError as e:
            print_logs(f"Error starting service: {str(e)}")
    elif run == "stopped":
        print_logs(f"Service {args.service_name} is not running. Attempting to start...")
        try:
            # Try to start the service
            subprocess.run(['pm2', 'start', args.service_name],
                           check=True, shell=True)

            # Get logs after restart
            logs = get_pm2_logs(args.service_name)
            # Create logs file attachment
            log_file = f"./logs/pm2_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            with open(log_file, 'w') as f:
                f.write(logs)

            # Send email notification
            send_email(log_file, f"Service {args.service_name} has been started", f"Service {args.service_name} has been started and logs are attached.")

            print_logs(f"Service {args.service_name} has been started and notification sent.")
        except subprocess.CalledProcessError as e:
            print_logs(f"Error starting service: {str(e)}")
    elif run == "stopped-error":
        print_logs(f"Service {args.service_name} is not running and the attempt to start failed...")
        try:
            # Get logs after restart
            logs = get_pm2_logs(args.service_name)
            # Create logs file attachment
            log_file = f"./logs/pm2_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            with open(log_file, 'w') as f:
                f.write(logs)

            # Send email notification
            send_email(log_file, f"Service {args.service_name} is not running and the attempt to start failed", f"Service {args.service_name} is not running and the attempt to start failed. Logs are attached.")

            print_logs(f"Service {args.service_name} has been started and notification sent.")
        except subprocess.CalledProcessError as e:
            print_logs(f"Error starting service: {str(e)}")
    else:
        print_logs(f"Service {args.service_name} is running.")


def update_code_base(cwd: str):
    try:
        # Check if service is running using pm2 jlist
        # subprocess.Popen(
        #     ['git', 'pull'], cwd=cwd, text=True, shell=True)
        result = subprocess.check_output(['git', 'pull'], shell=True, cwd=cwd)
        result = result.decode('utf-8')

        if 'Already up to date' in result:
            return 'up-to-date'
        else:
            return 'updated'
        
        
    except Exception as e:
        print_logs(f"Error updating code base: {str(e)}", True)
        return None


def build_and_update(service_name: str, package_manager: str, cwd: str = None):
    if not check_service_status(service_name):
        print_logs(f"Service {service_name} not found. Exiting...")
    else:
        print_logs(f"Service {service_name} found. Attempting to build...")
        try:
            print('cwd', cwd)
            if 'Already up to date' in update_code_base(cwd):
                print_logs('Code base is already up to date.')
                return False

            # Try to create the new build
            print_logs('Creating new build...')
            result_build = subprocess.check_output([package_manager, 'build'], cwd=cwd, shell=True)
            print(result_build)
            if 'Done in' not in str(result_build):
                print_logs('New build could not be created. Exiting...')
                return False
            
            # Try to stop the service
            print_logs('Stopping service...')
            subprocess.run(['pm2', 'stop', service_name], check=True, shell=True)
            if check_service_status(service_name) != "stopped":
                print_logs('Service could not be stopped. Exiting...')
                return False
            
            print_logs(f"Service {service_name} has been stopped.\nUpdating production build...")

            result_update_build = subprocess.check_output([package_manager, 'update_build'], cwd=cwd, shell=True)
            print(result_update_build)
            if 'Done in' not in str(result_update_build):
                print_logs('Production build could not be updated. Exiting...')
                return False
            
            # Try to restart the service
            print_logs('Build updated successfully. Restarting service...')
            subprocess.run(['pm2', 'start', service_name], check=True, shell=True)
            if check_service_status(service_name) == "stopped":
                print_logs('Service could not be restarted. Exiting...')
                return False

            return True
            
        except subprocess.CalledProcessError as e:
            print_logs(f"Error updating service: {str(e)}", True)
            return False

try:
    jsonArg = json.loads(sys.argv[1].replace("'", '"'))
    # jsonArg = json.loads("{'function': 'check_service_status', 'config_file_path': 'C:/Users/vitor.vasconcelos/code/integratis-2/pm2.config.js', 'service_name': 'integratis-dev'}".replace("'", '"'))
    jsonArg = Args(
        function=jsonArg['function'] if 'function' in jsonArg.keys() else '',
        check_service_status=jsonArg['check_service_status'] if 'check_service_status' in jsonArg.keys() else '',
        package_manager=jsonArg['package_manager'] if 'package_manager' in jsonArg.keys() else '',
        config_file_path=jsonArg['config_file_path'] if 'config_file_path' in jsonArg.keys() else '',
        service_name=jsonArg['service_name'] if 'service_name' in jsonArg.keys() else '',
        cwd=jsonArg['cwd'] if 'cwd' in jsonArg.keys() else ''
    )
except Exception as e:
    print_logs(f"Parameter is invalid: {e}", True)
    jsonArg = None

if __name__ == "__main__":
    try:
        if jsonArg.function == 'check_service_status':
            check_and_run(jsonArg)
        
        elif jsonArg.function == 'update_build':
            package_manager = jsonArg.package_manager if 'package_manager' in jsonArg else 'npm'

            if not jsonArg.cwd:
                raise Exception("cwd is required for update_build")

            deploy_result = build_and_update(jsonArg.service_name, package_manager, jsonArg.cwd)

            if deploy_result:
                send_email(f"./logs/log_print_{datetime.now().strftime('%Y%m%d')}.txt", f'''New build for {jsonArg.service_name} deployed''',  f'''New build for {jsonArg.service_name} deployed!''' )
            else:
                print_logs(f'''The build for {jsonArg.service_name} could not be deployed, please check the logs!''', True)

    except Exception as err:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error = f"There was an error trying to execute the server handler. \nError: {str(err)}", f" | Traceback: {exc_type} | File: {fname} | Line error: {exc_tb.tb_lineno}"
        print_logs(error, True)


# py main.py "{'function': 'check_service_status', 'service_name': 'integratis-dev'}"
# py main.py "{'function': 'update_build', 'service_name': 'integratis-dev', 'package_manager': 'yarn', 'cwd': 'C:\\Users\\vitor.vasconcelos\\code\\integratis-2'}"
# "C:\server-handler\main.py" "{'function': 'check_service_status', 'config_file_path': 'C:/integratis-2/pm2.config.js', 'service_name': 'integratis-prod'}"
# "C:\Users\vitor.vasconcelos\code\server-handler\main.py" "{'function': 'check_service_status', 'config_file_path': 'C:/Users/vitor.vasconcelos/code/integratis-2/pm2.config.js', 'service_name': 'integratis-dev'}"
