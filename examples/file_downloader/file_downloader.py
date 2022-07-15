import onscale_client as cloud

import getpass
import getopt
import sys
import os


def main(argv):
    username = None
    password = None
    portal = None
    job_id = None
    dl_path = ""

    try:
        opts, args = getopt.getopt(argv, "", ["help", "user=", "pass=", "portal="])
    except getopt.GetoptError:
        print(
            "file_downloader.py --user <username> \
--pass <password> --portal <test|dev|prod> --job_id <job id> --dir <dl directory>"
        )
        sys.exit(2)

    for opt, arg in opts:
        if opt == "-h":
            print(
                "file_downloader.py --user <username> \
--pass <password> --portal <test|dev|prod> --job_id <job id> --dir <dl directory>"
            )
            sys.exit()
        elif opt in ("--user"):
            username = arg
        elif opt in ("--pass"):
            password = arg
        elif opt in ("--portal"):
            portal = arg
        elif opt in ("--job_id"):
            job_id = arg
        elif opt in ("--dir"):
            dl_path = arg

    user_dir = os.path.expanduser(f"~{getpass.getuser()}")
    onscale_dir = os.path.join(user_dir, ".onscale")
    config_file = os.path.join(onscale_dir, "config")

    if not os.path.exists(config_file):
        if username is None or len(username) == 0:
            username = input("Username:")
        if password is None or len(password) == 0:
            password = getpass.getpass()
        if portal is None or len(portal) == 0 or portal not in ("dev", "test", "prod"):
            portal = input("Portal (test|dev|prod):")

    if job_id is None or len(job_id) == 0:
        job_id = input("Job ID [Last Job]:")
        if job_id == "":
            job_id = None

    client = cloud.Client(user_name=username, password=password, portal_target=portal)

    if job_id is None:
        job = client.get_last_job()
    else:
        job = client.get_job(job_id)

    if dl_path == "" or dl_path == ".":
        dl_path = os.getcwd()

    job.download_all(dl_path)


if __name__ == "__main__":
    main(sys.argv[1:])
