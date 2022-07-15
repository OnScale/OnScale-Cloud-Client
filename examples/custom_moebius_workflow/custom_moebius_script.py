import onscale_client as cloud
import os

# Set the portal you have setup the moebius job and estuimated using
# the OnScale Solve UI
PORTAL = "Test"
# specify the JobId which corresponds to the model estimated on solve
JOB_ID = ""
# specify the download directory. os.getcwd() specifies the current
# working directory
DL_DIR = os.getcwd()

# Get a list of the available profiles for the given portal
profiles = cloud.get_available_profiles(portal_target=PORTAL)

# Create a Client instance which will use the desired profile for
# the given target. You must ensure the profile selected is the
# same as the account which set up the model.
client = cloud.Client(alias=profiles[0], portal_target=PORTAL)

# request the last job which has been created
job = client.get_last_job()

# download the input file for the created job
job.download_file(file_name=f"{job.job_id}.py", download_dir=DL_DIR)

# TODO -Edit the input file which has been downloaded

# upload the edited file to the job
job.upload_file(filename=os.path.join(DL_DIR, f"{job.job_id}.py"))

# upload any accompanying files which may now be required to complete
# the simulation
job.upload_file(filename="path_to_accompanying_file")
