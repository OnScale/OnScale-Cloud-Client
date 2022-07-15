.. _job_progress:

===========
JobProgress
===========

.. currentmodule:: onscale_client

SimProgress Object tracking and displaying progress information for a given simulation

SimProgress Defintions
==========================
.. autoclass:: SimProgress
    :members: update_progress, update_status, completed


JobProgressManager Object allowing progress of all of the simulations for this job to be tracked

JobProgressManager Defintions
=================================
.. autoclass:: JobProgressManager
    :members: sim_exists, add_simulation, set_progress, set_status, complete, finish
