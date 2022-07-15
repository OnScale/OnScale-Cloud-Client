from typing import Dict, Optional
from .common.client_settings import import_tqdm_notebook

if import_tqdm_notebook():
    from tqdm.notebook import tqdm  # type: ignore
else:
    from tqdm import tqdm  # type: ignore


class SimProgress(object):
    """Object to track, update and display simulation progress

    :param object: [description]
    :type object: [type]
    """

    def __init__(
        self, sim_id: str, progress_value: int, index: int, status: str = "QUEUED"
    ):
        self.sim_id = sim_id
        self.progress_value = progress_value
        self.status = status
        self.progress_bar = tqdm(
            total=100,
            desc=f"{sim_id}:",
            bar_format="{l_bar}|{bar}|{n_fmt}/{total_fmt}",
            position=index,
        )

    def update_progress(self, progress_value: int):
        """Update the stored progress value and accompanying progress bar

        Args:
          progress_value: the simulation progress after update
        """
        self.progress_bar.update(progress_value - self.progress_value)
        self.progress_value = progress_value

    def update_status(self, status: str):
        """Update the curretn simulation status"""
        self.status = status

    def completed(self):
        """mark this simulation as completed"""
        return self.status == "COMPLETE" and self.progress_value == 100


class JobProgressManager(object):
    """A manager class for tracking Simulation progress for a Job."""

    def __init__(self):
        self.progress_map: Dict[SimProgress] = dict()

    def sim_exists(self, sim_id: str) -> bool:
        """returns True if the given simulation is being tracked

        Args:
          sim_id: the UUID of the simulation to check existence of
        """
        return sim_id in self.progress_map

    def add_simulation(self, sim_id: str):
        """Adds a simulation for tracking within the manager class

        Args:
          sim_id: the UUID of the simulation to track within the manager
        """
        index = len(self.progress_map)
        self.progress_map[sim_id] = SimProgress(
            sim_id=sim_id, progress_value=0, index=index
        )

    def set_progress(self, sim_id: str, progress_val: int):
        """Update the progress value for a simulation within the manager

        Args:
          sim_id: the UUID corresponding to the simulation to update
          progress_val: The updated progress value
        """
        self.progress_map[sim_id].update_progress(progress_val)

    def set_status(self, sim_id: str, status: str):
        """Update the status value for a simulation within the manager

        Args:
          sim_id: the UUID corresponding to the simulation to update
          status: The updated status
        """
        self.progress_map[sim_id].update_status(status)

    def complete(self, sim_id: Optional[str] = None):
        """Mark a simulation as complete within the Progress Manager

        Args:
          sim_id: the UUID corresponding to the simulation to update
        """
        if sim_id is not None:
            if sim_id in self.progress_map.keys():
                return self.progress_map[sim_id].completed()
        else:
            for _, p in self.progress_map.items():
                if not p.completed():
                    return False
            return True

    def finish(self) -> bool:
        """Function to check if a Job is completed"""
        for _, p in self.progress_map.items():
            if not p.completed():
                return False
            else:
                p.progress_bar.close()
        return True
