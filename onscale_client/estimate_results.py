from .estimate_data import EstimateData


class EstimateResults:
    """EstimateResults class used to store and operate on the results which are returned
    from the process of estimation."""

    def __init__(self, **kwargs):
        self.estimate_id = kwargs["estimateId"]
        self.number_of_cores = kwargs["numberOfCores"]
        self.estimated_memory = kwargs["estimatedMemory"]
        self.estimated_run_times = kwargs["estimatedRunTimes"]
        self.parts_count = kwargs["partsCount"]
        self.type = kwargs["type"]
        self.estimate_hashes = kwargs["estimateHashes"]
        self.parameters = kwargs["parameters"]

    def __str__(self):
        return_str = "EstimateResults(\n"
        return_str += f"    estimate_id={self.estimate_id}\n"
        return_str += f"    number_of_cores={self.number_of_cores}\n"
        return_str += f"    estimated_memory={self.estimated_memory}\n"
        return_str += f"    estimated_run_times={self.estimated_run_times}\n"
        return_str += f"    parts_count={self.parts_count}\n"
        return_str += f"    type={self.type}\n"
        return_str += f"    estimate_hashes={self.estimate_hashes}\n"
        return_str += f"    parameters={self.parameters}\n"
        return_str += ")"
        return return_str

    def __repr__(self) -> str:
        attrs = list()
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            elif v is None:
                continue
            else:
                attrs.append(f"{k}={str(v)}")
        joined = ", ".join(attrs)
        return f"{type(self).__name__}({joined})"

    def get_nearest_estimate(self, max_spend: int, number_of_parts: int = None):
        """Return the nearest estimate data to a given max_spend value

        Iterates through the returend estimation results and finds the result which
        is closest to, without exceeding, the max_spend value passed in as an argumet.
        This function can be used to find the most appropriate settings to use for a
        sepcific spending limit.

        Args:
            max_spend (int): The maximum amount of core hours to spend on the associated
                job
            number_of_parts (int): The desired number of parts to run this simulation using.
                If specified the estimate returned will have at least the value specified as
                the number of parts to use for this simulation.

        Returns:
            A data structure which will hold the values which correspond
                with the argument passed in for max_spend.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.create_job(job_name='new_job')
            >>>
            >>> simapi_blob_id = job.upload_blob(on.files.BlobType.SimApi.value,
            ...                                  '/tmp/simulation.py')
            >>> cad_blob_id = job.upload_blob(on.files.BlobType.Cad.value,
            ...                               '/tmp/cad_file.stp')
            >>> meta_data = self._generate_simapi_metadata_json(/tmp,
            ...                                                 '/tmp/cad_file.stp',
            ...                                                 cad_blob_id)
            >>> job.upload_blob_child(simapi_blob_id,
            ...                       on.files.ChildBlobType.SimMetaData.value,
            ...                       meta_data)
            ...
            >>> job.estimate(sim_api_blob_id=simapi_blob_id,
            ...              docker_tag=docker_tag,
            ...              precision=precision)
            ...
            >>> if job.estimate_results is not None:
            ...     estimate_data = job.estimate_results.get_nearest_estimate(
            ...        max_spend=2)
            >>> print(estimate_data.cost)
            0.012
        """
        returnData = None
        for idx in range(len(self.number_of_cores)):
            curr_parts = 0
            if self.parts_count is not None:
                curr_parts = self.parts_count[idx]
            # core count is 2 * parts for MNMPI
            curr_cores = (
                curr_parts * 2 if curr_parts > 31 else self.number_of_cores[idx]
            )
            if curr_cores % 2 > 0:
                curr_cores = curr_cores + 1
            curr_parts = curr_cores // 2

            total_cost = self.number_of_cores[idx] * (
                self.estimated_run_times[idx] / 3600
            )
            if total_cost < max_spend:
                if number_of_parts is None or curr_parts >= number_of_parts:
                    if returnData is None or returnData.cost > total_cost:
                        returnData = EstimateData(
                            id=self.estimate_id,
                            cores=curr_cores,
                            memory=self.estimated_memory[idx],
                            run_time=self.estimated_run_times[idx],
                            parts=curr_parts,
                            type=self.type,
                            hash=self.estimate_hashes[idx],
                            cost=total_cost,
                            parameters=self.parameters,
                        )
        # if an estimate at the number of parts requested could not be found then work
        # work backward from the number of parts requested to find the closest one
        if returnData is None:
            for idx in reversed(range(len(self.number_of_cores))):
                curr_parts = 0
                if self.parts_count is not None:
                    curr_parts = self.parts_count[idx]
                # core count is 2 * parts for MNMPI
                curr_cores = (
                    curr_parts * 2 if curr_parts > 31 else self.number_of_cores[idx]
                )
                if curr_cores % 2 > 0:
                    curr_cores = curr_cores + 1
                curr_parts = curr_cores // 2

                total_cost = self.number_of_cores[idx] * (
                    self.estimated_run_times[idx] / 3600
                )
                if total_cost < max_spend:
                    if number_of_parts is None or curr_parts <= number_of_parts:
                        if returnData is None or returnData.cost > total_cost:
                            returnData = EstimateData(
                                id=self.estimate_id,
                                cores=curr_cores,
                                memory=self.estimated_memory[idx],
                                run_time=self.estimated_run_times[idx],
                                parts=curr_parts,
                                type=self.type,
                                hash=self.estimate_hashes[idx],
                                cost=total_cost,
                                parameters=self.parameters,
                            )
        return returnData

    def get_lowest_core_hour_spend(self, number_of_parts: int = None):
        """Return the Estimate data with the loest core hour spend

        Iterates through the returend estimation results and finds the result which
        will give the lowest core hour spend. This function can be used to find the
        most appropriate settings to use for a sepcific spending limit.

        Args:
          number_of_parts (int): The desired number of parts to run this simulation using.
            If specified the estimate returned will have at least the value specified as
            the number of parts to use for this simulation.

        Returns:
            A data structure which will hold the values of the estimate
            which will have the lowest core hour spend.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.get_job(job_name='my_job')
            >>>
            >>> simapi_blob_id = job.upload_blob(on.files.BlobType.SimApi.value,
            ...                                  '/tmp/simulation.py')
            >>> cad_blob_id = job.upload_blob(on.files.BlobType.Cad.value,
            ...                               '/tmp/cad_file.stp')
            >>> meta_data = self._generate_simapi_metadata_json(/tmp,
            ...                                                 '/tmp/cad_file.stp',
            ...                                                 cad_blob_id)
            >>> job.upload_blob_child(simapi_blob_id,
            ...                       on.files.ChildBlobType.SimMetaData.value,
            ...                       meta_data)
            ...
            >>> job.estimate(sim_api_blob_id=simapi_blob_id,
            ...              docker_tag=docker_tag,
            ...              precision=precision)
            ...
            >>> if job.estimate_results is not None:
            ...     estimate_data = job.estimate_results.get_lowest_core_hour_spend()
            >>> print(estimate_data.cost)
            0.01
            >>> print(estimate_data.run_time)
            0.25
        """
        returnData = None
        for idx in range(len(self.number_of_cores)):
            curr_parts = self.parts_count[idx]
            # core count is 2 * parts for MNMPI
            curr_cores = (
                curr_parts * 2 if curr_parts > 31 else self.number_of_cores[idx]
            )

            lowest_cost = self.number_of_cores[idx] * (
                self.estimated_run_times[idx] / 3600
            )
            if number_of_parts is None or curr_parts >= number_of_parts:
                if returnData is None or returnData.cost < lowest_cost:
                    returnData = EstimateData(
                        id=self.estimate_id,
                        cores=curr_cores,
                        memory=self.estimated_memory[idx],
                        run_time=self.estimated_run_times[idx],
                        parts=curr_parts,
                        type=self.type,
                        hash=self.estimate_hashes[idx],
                        cost=lowest_cost,
                        parameters=self.parameters,
                    )
        return returnData

    def get_quickest_run_time(self, number_of_parts: int = None):
        """Return the Estimate data with the loest core hour spend

        Iterates through the returend estimation results and finds the result which
        will give the quicekst estimated run time. This function can be used to find the
        most appropriate settings to retrieve results quickly.

        Args:
          number_of_parts (int): The desired number of parts to run this simulation using.
            If specified the estimate returned will have at least the value specified as
            the number of parts to use for this simulation.

        Returns:
            A data structure which will hold the values of the estimate
            which will have the lowest estimated run time.

        Example:
            >>> import onscale_client as os
            >>> client = os.Client()
            >>> job = client.get_job(job_name='my_job')
            >>>
            >>> simapi_blob_id = job.upload_blob(on.files.BlobType.SimApi.value,
            ...                                  '/tmp/simulation.py')
            >>> cad_blob_id = job.upload_blob(on.files.BlobType.Cad.value,
            ...                               '/tmp/cad_file.stp')
            >>> meta_data = self._generate_simapi_metadata_json(/tmp,
            ...                                                 '/tmp/cad_file.stp',
            ...                                                 cad_blob_id)
            >>> job.upload_blob_child(simapi_blob_id,
            ...                       on.files.ChildBlobType.SimMetaData.value,
            ...                       meta_data)
            ...
            >>> job.estimate(sim_api_blob_id=simapi_blob_id,
            ...              docker_tag=docker_tag,
            ...              precision=precision)
            ...
            >>> if job.estimate_results is not None:
            ...     estimate_data = job.estimate_results.get_quickest_run_time()
            >>> print(estimate_data.cost)
            1.04
            >>> print(estimate_data.run_time)
            0.02
        """
        returnData = None
        for idx in range(len(self.number_of_cores)):
            curr_parts = self.parts_count[idx]
            # core count is 2 * parts for MNMPI
            curr_cores = (
                curr_parts * 2 if curr_parts > 31 else self.number_of_cores[idx]
            )

            quickest_run_time = self.estimated_run_times[idx]
            if number_of_parts is None or curr_parts >= number_of_parts:
                if returnData is None or returnData.run_time < quickest_run_time:
                    calculated_cost = curr_cores * (
                        self.estimated_run_times[idx] / 3600
                    )
                    returnData = EstimateData(
                        id=self.estimate_id,
                        cores=curr_cores,
                        memory=self.estimated_memory[idx],
                        run_time=self.estimated_run_times[idx],
                        parts=curr_parts,
                        type=self.type,
                        hash=self.estimate_hashes[idx],
                        cost=calculated_cost,
                        parameters=self.parameters,
                    )
