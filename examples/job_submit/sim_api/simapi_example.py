"""
    Auto-generated simulation code.
"""
import onscale as on

with on.Simulation("Swing Arm", "None") as sim:

    # Define geometry
    geometry = on.CadFile("swing_arm_2.step")

    # Define material database and materials
    materials = on.CloudMaterials("onscale")
    steel = materials["steel"]
    steel >> geometry.parts[0]

    # Define and apply loads
    fixed = on.loads.Fixed()
    fixed >> geometry.parts[0].faces[496]
    fixed >> geometry.parts[0].faces[373]
    force = on.loads.Force(1000, [0, 0, -1])
    force >> geometry.parts[0].faces[340]
    force >> geometry.parts[0].faces[191]

    # Define meshing
    on.meshes.MeshFile("")

    # Define output variables
    on.fields.Displacement()
    on.fields.Stress()
    on.fields.Strain()

import onscale_client as cloud
import time
import os

client = cloud.Client()

lf = cloud.LinkedFile(
    job_id="710c771b-3ebf-4344-9ce0-ba2feb123956",
    file_name="medium_volume_mesh.msh",
    file_alias="medium_volume_mesh.msh",
)

new_job = client.submit(
    input_obj=sim, max_spend=5, job_name=f"sim_submission_test_{time.time()}"
)

# poll the status until the status is finished
status_str = new_job.status()
while status_str != "FINISHED":
    print("Current Status: [%s]" % status_str, end="\r")
    time.sleep(30)
    status_str = new_job.status()

print("Current Status: [FINISHED]")

# download results to the current working directory
print(f"downloading files for {new_job.job_id}")
new_job.download_results(os.path.join(os.getcwd(), "results"))
