"""
    Auto-generated simulation code for MOEBIUS.

    Run as: mpirun -np X python3 moebius_simulate.py

"""

import MagicUniverse
import argparse


def simulate():

    # Universe simulation settings

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--spacing",
        required=True,
        default=None,
        help="finest voxel spacing in meters",
    )
    parser.add_argument(
        "-l",
        "--lchar",
        required=True,
        default=None,
        help="characteristic length in meters",
    )
    parser.add_argument(
        "-C",
        "--continueOnVersionMismatch",
        required=False,
        action="store_true",
        help="continue on ltu/backend version mismatch",
    )
    parser.add_argument(
        "-D",
        "--debugMode",
        required=False,
        action="store_false",
        help="run in debug mode",
    )
    parser.add_argument(
        "-P",
        "--progressReport",
        required=False,
        action="store_false",
        help="Progress report in json format",
    )
    args = parser.parse_args()

    u = MagicUniverse.Universe()

    if u.retrieveMyproc() == 0:
        print("ARGS:", args)

    u.setUniversePath("/tmp/template.ltu")
    u.setCasePath("/tmp/template.ltc")

    u.setProgressReport(True)
    u.setUnits("MKS")
    spc = float(args.spacing)
    lchar = float(args.lchar)
    u.setFinestResolution(spc)
    u.setCharacteristicValues(
        Length=lchar, Velocity=1.0, Pressure=0.0, Mach=0.06956635688164886, Density=1000
    )

    u.setSimulationTime(0.01)
    u.setStateRestart(False)
    u.setStateDump(frequency=0.01)

    # Scale settings
    scale_0 = u.nextScale()
    vmesh_0 = u.nextMesh(scale_0)
    fluid_0 = u.nextFluid(scale_0)
    track_0 = u.nextTracker(scale_0)

    # Define simulation tracking
    track_0.setDiagnosticDeltaStep(10)
    track_0.setVtkDump(frequency=0.001)

    # Define volumetric meshing
    vmesh_0.setDomainDecomposition("Automatic")

    # Define fluid settings
    fluid_0.setViscosity(1e-06)
    fluid_0.setDensityUniform(1000)
    fluid_0.setVtkIncludeDensity(False)
    fluid_0.setTurbulenceSGS(True)
    fluid_0.setWallTurbulence(False)

    u.decorate()

    # Define boundary conditions
    fluid_0.setBC(ioid=1, bctype="pressure", val=0.0)  # Outlet 1
    fluid_0.setBC(
        ioid=2, bctype="velocity", val_dir=[-1.0, 1.394229542445967e-17, 0.0], val=1.0
    )  # Inlet 1

    # Define temporal animation
    for itime in u.cycle():
        u.animate()


if __name__ == "__main__":
    MagicUniverse.MagicBegins()

    try:
        simulate()

    except BaseException as e:
        print(e)

    MagicUniverse.MagicEnds()
