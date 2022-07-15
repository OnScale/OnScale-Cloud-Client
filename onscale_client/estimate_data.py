class EstimateData:
    """Data structure to store individual estimate data"""

    def __init__(self, **kwargs):
        self.id = kwargs["id"] if "id" in kwargs else None
        self.cores = kwargs["cores"]
        self.memory = kwargs["memory"]
        self.run_time = kwargs["run_time"] if "run_time" in kwargs else None
        self.parts = kwargs["parts"] if "parts" in kwargs else None
        self.hash = kwargs["hash"] if "hash" in kwargs else None
        self.cost = kwargs["cost"] if "cost" in kwargs else None
        self.type = kwargs["type"] if "type" in kwargs else None
        self.parameters = kwargs["parameters"] if "parameters" in kwargs else None

        self._validate()

    def set_data(self, **kwargs):
        """Sets the Estimate data using the args passed"""
        self.id = kwargs["id"]
        self.cores = kwargs["cores"]
        self.memory = kwargs["memory"]
        self.run_time = kwargs["run_time"]
        self.parts = kwargs["parts"]
        self.hash = kwargs["hash"]
        self.cost = kwargs["cost"]
        self.type = kwargs["type"]
        self.parameters = kwargs["parameters"]

        self._validate()

    def _validate(self):
        """Validates that all of the estimate data has been populated properly"""
        if self.cores is None:
            raise ValueError("Invalid Estimate Cores")
        if self.memory is None:
            raise ValueError("Invalid Estimate Memory Value")
        if self.cost is None:
            raise ValueError("No Cost value defined for this estimate")

    def __str__(self):
        """string representation of EstimateData object"""
        return_str = "EstimateData(\n"
        return_str += f"    id={self.id},\n"
        return_str += f"    cores={self.cores},\n"
        return_str += f"    memory={self.memory},\n"
        return_str += f"    run_time={self.run_time},\n"
        return_str += f"    parts={self.parts},\n"
        return_str += f"    hash={self.hash},\n"
        return_str += f"    cost={self.cost},\n"
        return_str += f"    type={self.type},\n"
        return_str += f"    parameters={self.parameters},\n"
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
