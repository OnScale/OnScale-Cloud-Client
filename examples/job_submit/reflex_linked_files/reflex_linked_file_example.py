import os
import onscale_client as cloud


if __name__ == "__main__":

    # get file paths for input files
    directory = os.path.dirname(os.path.realpath(__file__))
    input_file = os.path.join(directory, "input_file.json")

    # initialise the cloud client
    client = cloud.Client()

    # set up the linked files
    lf = cloud.LinkedFile(
        job_id="73fd2795-9280-4ded-8e04-6c76ce1e49fa",
        file_name="medium_mesh_volume.msh",
        file_alias="medium_mesh_volume.msh",
    )

    # submit a job with specified
    new_job = client.submit(
        input_obj=input_file,
        max_spend=5,
        linked_files=[lf],
        job_name="reflex_linked_file_test",
        precision="DOUBLE",
        ram=16000,
        cores=4,
        core_hour_estimate=5,
        number_of_parts=2,
    )
