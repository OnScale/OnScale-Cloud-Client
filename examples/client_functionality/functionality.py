import onscale_client as cloud
from onscale_client.configure import (
    get_available_profiles,
    get_config_account_name,
    get_config_developer_token,
    get_config_portal,
)

""" This is a test script that shodul exercise all of the Configure,
    Client, Job and Simulation functionality. The script requires a profile
    defined for the user.

    It can be used to ensure that no exceptions or failures have been
    introduced but doesnt validate any results. This would have to be
    done manually """


client = cloud.Client(alias="test_US")
job = client.get_last_job()
print(job)

exercise_config = True
exercise_client = True
exercise_job = False
exercise_simulation = False
exercise_account = False

job = None


if exercise_config:
    print("*** get_available_profiles() ***")
    print(get_available_profiles())
    print("*** get_config_account_name() ***")
    print(get_config_account_name())
    print("*** get_config_developer_token() ***")
    print(get_config_developer_token())
    print("*** get_config_portal() ***")
    print(get_config_portal())

if exercise_client:
    print("*** client.current_account_id() ***")
    print(client.current_account_id)
    print("*** client.current_account_name() ***")
    print(client.current_account_name)
    print("*** client.current_account() ***")
    print(client.current_account)

    print("*** client.account_names() ***")
    print(client.account_names())
    print("*** client.account_ids() ***")
    print(client.account_ids())
    print("*** client.available_hpc_clouds() ***")
    print(client.available_hpc_clouds())
    print("*** client.available_hpc_regions() ***")
    print(client.available_hpc_regions())

    print('*** client.account_exists("My Account") ***')
    print("True") if client.account_exists("My Account") else print("False")
    print('*** client.account_exists("OnScale UK") ***')
    print("True") if client.account_exists("My Account") else print("False")

    print("*** client.get_available_materials() ***")
    print(client.get_available_materials())

    print('*** client.get_hpc_id_from_cloud("AWS") ***')
    print(client.get_hpc_id_from_cloud("AWS"))
    print('*** client.get_hpc_id_from_cloud("GCP") ***')
    print(client.get_hpc_id_from_cloud("GCP"))
    print('*** client.get_hpc_id_from_cloud("Alibaba") ***')
    print(client.get_hpc_id_from_cloud("Alibaba"))

    print("*** client.get_hpc_list(client.current_account_id) ***")
    print(client.get_hpc_list(client.current_account_id))

    print("*** client.get_job_list() ***")
    print(client.get_job_list(job_count=30))
    print("*** client.get_job_history() ***")
    print(client.get_job_history())

if exercise_job:
    print("*** client.get_last_job() ***")
    job = client.get_last_job()
    print("*** job.blob_list() ***")
    blob_list = job.blob_list()
    for b in blob_list:
        print(b.__dict__)
    print("*** job.blob_list() ***")
    file_list = job.file_list()
    for f in file_list:
        print(f.__dict__)
    print("*** job.get_progress() ***")
    print(job.get_progress())
    print("*** job.get_simulation_progress() ***")
    print(job.get_simulation_progress())
    print("*** job.job_name ***")
    job_name = job.job_name
    print(job_name)
    print("*** job.rename('renamed_job') ***")
    job.rename("renamed_job")
    print("*** job.job_name() ***")
    print(job.job_name)
    print("*** job.rename('original name') ***")
    job.rename(job_name)
    print("*** job.job_name() ***")
    print(job.job_name)
    print("*** job.tags() ***")
    tag_list = job.tags
    print(tag_list)
    print("*** job.tag('Tag 1') ***")
    job.tag("Tag 1")
    print("*** job.tags() ***")
    job._populate_tag_list()
    tag_list = job.tags
    print(tag_list)
    print("*** job.tag('Tag 2') ***")
    job.tag("Tag 2")
    tag_list = job.tags
    print("*** job.tags() ***")
    job._populate_tag_list()
    tag_list = job.tags
    print(tag_list)
    print("*** job.untag('Tag 1') ***")
    job.untag("Tag 1")
    tag_list = job.tags
    print("*** job.tags() ***")
    job._populate_tag_list()
    tag_list = job.tags
    print(tag_list)

    import os

    job.download_all(os.path.join(os.getcwd(), "test", "job"))

if exercise_simulation:
    import os

    if not job:
        job = client.get_last_job()

    if job.simulations:
        sim = job.simulations[0]

        file_list = sim.file_list()
        for f in file_list:
            print(f.__dict__)

        sim.download_all(os.path.join(os.getcwd(), "test", "sim"))
