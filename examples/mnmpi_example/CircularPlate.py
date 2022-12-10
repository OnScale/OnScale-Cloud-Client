"""
    Auto-generated simulation code.
"""
import onscale as on

with on.Simulation("None", "None") as sim:

    on.settings.EnabledPhysics(["mechanical"])
    geometry = on.CadFile("CircPlate_Quarter.step")

    materials = on.CloudMaterials("onscale")
    steel = materials["Structural steel"]
    steel >> geometry.parts[0]

    # Define and apply loads
    pressure = on.loads.Pressure(250e3, alias="LoadedArea")
    pressure >> geometry.parts[0].faces[2]
    restraint = on.loads.Restraint(x=True, y=True, z=True, alias="CircumFace")
    restraint >> geometry.parts[0].faces[4]
    symmetry = on.loads.Symmetry(alias="NXFace")
    symmetry >> geometry.parts[0].faces[5]
    symmetry_2 = on.loads.Symmetry(alias="NYFace")
    symmetry_2 >> geometry.parts[0].faces[3]

    # Define probes
    probe1 = on.Point(x=55.0272, y=59.3952, z=1.5)
    on.probes.Displacement(probe1)
    probe2 = on.Point(x=35.7692, y=12.0066, z=1.5)
    on.probes.Displacement(probe2)

    # Define output variables
    on.fields.Displacement()
    on.fields.Stress()
    on.fields.Strain()
    on.fields.VonMises()
    on.sensors.ReactionSensor() >> restraint    

import onscale_client as client
import time

client = client.Client()

# set account to desired account if required
# client.set_current_account(account_name="OnScale UK")
# client.set_current_account(account_name='OnScale US')

job = client.submit(
    input_obj=sim,
    max_spend=5,
    job_name=f"circular_plate_submission_test_{time.time()}",
    number_of_parts=60
)

# if the job successfully committed poll status and progress
print(f"waiting for {job.job_name} with id {job.job_id}...")
while True:
    status = job.status()
    print(f"{status}--{job.get_progress()}%")
    if status == "FINISHED":
        break
    time.sleep(10)

# download results
job.download_results("downloads")
print("results donwloaded in directory 'downloads'")
