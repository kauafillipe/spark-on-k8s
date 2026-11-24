import argparse
from export_s3 import export_s3


def get_args(args_list: list) -> dict:  # diff 1
    """
    Generate dictionary with all parsed arguments
    :param args_list: list of arguments. Ex: ["domain", "data_product", "dataset"]
    :return: kwargs. Dictionary with all arguments parsed
    """
    parser = argparse.ArgumentParser()
    for arg in args_list:
        parser.add_argument(f"--{arg}", required=True)
    return vars(parser.parse_args())


JOB_ARGUMENTS = get_args(args_list=["bucket", "domain", "data_product", "dataset"])

BUCKET = JOB_ARGUMENTS.get("bucket")
DOMAIN = JOB_ARGUMENTS.get("domain")
DATA_PRODUCT = JOB_ARGUMENTS.get("data_product")
DATASET = JOB_ARGUMENTS.get("dataset")


export_s3(
    bucket=BUCKET,
    domain=DOMAIN,
    data_product=DATA_PRODUCT,
    dataset=DATASET,
)
