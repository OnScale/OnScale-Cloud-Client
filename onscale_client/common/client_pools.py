from enum import Enum, unique


@unique
class PortalTarget(Enum):
    """NOTE: defines the portal target."""

    Test = "test"
    Development = "dev"
    Production = "prod"
    LIST = ["test", "dev", "development", "prod", "production"]


@unique
class PortalHost(Enum):
    """NOTE: all the urls the user may login to."""

    Test = "https://test.portal.onscale.com/api"
    Development = "https://dev.portal.onscale.com/api"
    Production = "https://prod.portal.onscale.com/api"


@unique
class ClientDevelopmentPools(Enum):
    """NOTE: client this class if you're connecting to the development portal"""

    PoolId = "us-east-1_CrB4zbqmu"
    PoolWebClientId = "7uhflf2megm48u2m7fte5g8eq3"
    PoolRegion = "us-east-1"


@unique
class ClientProductionPools(Enum):
    """NOTE: use this class if you're connecting to teh production portal"""

    PoolId = "us-east-1_CrB4zbqmu"
    PoolWebClientId = "7uhflf2megm48u2m7fte5g8eq3"
    PoolRegion = "us-east-1"


@unique
class ClientTestPools(Enum):
    """NOTE: use this class if you're connecting to the test portal"""

    PoolId = "us-east-1_OMUB8v30W"
    PoolWebClientId = "1ve5l4rl2mrb74b1cbdjgjqdi5"
    PoolRegion = "us-east-1"
