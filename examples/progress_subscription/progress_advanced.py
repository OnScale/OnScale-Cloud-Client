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
    on.meshes.BasicMedium()

    # Define output variables
    on.outputs.Displacement()
    on.outputs.Stress()
    on.outputs.Strain()

import onscale_client as os_client
import time

client = os_client.Client()

# set account to desired account if required. See below
client.set_current_account(account_name="OnScale UK")

new_job = client.submit(
    input_obj=sim, max_spend=1, job_name=f"sim_submission_test_{time.time()}"
)


def on_job_progress(msg: str):
    print(msg)


def on_job_finished(msg: str):
    print(msg)


socket_thread = os_client.sockets.JobWebsocketThread(
    portal=new_job._portal,
    client_token=new_job._token,
    job_id=new_job.job_id,
    on_progress=on_job_progress,
    on_finished=on_job_finished,
)
with socket_thread:
    print("Monitoring progress. Press Ctrl+C to cancel")
    try:
        print("Awaiting connection... ")
        while not socket_thread.job_finished:
            tick = time.time()
            while not socket_thread.message_received:
                if time.time() - tick > 600:
                    print("Progress timed out...")
                    break
                time.sleep(0.5)
            socket_thread.message_received = False

    except KeyboardInterrupt:
        socket_thread.message_received = True
        socket_thread.job_finished = True
        print("Terminating progress...")

    socket_thread.kill()
