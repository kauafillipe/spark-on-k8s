import boto3
import logging
from pathlib import Path
import shutil

from pyspark.sql import SparkSession

logging.getLogger().setLevel(logging.INFO)

BUCKET_EXPORTER = "/spark-output"  # diff 2


def get_dynamodb_item(id: str) -> dict:
    """
    Retrieves an item from a DynamoDB table based on its ID.

    :param id : The ID of the item to be retrieved.
    :returns: The item from the DynamoDB table as a dictionary.
    """
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    dynamodb_table = dynamodb.Table("dataflash_export_s3")

    return dynamodb_table.get_item(Key={"id": id})["Item"]


def export_s3(
    bucket: str,
    domain: str,
    data_product: str,
    dataset: str,
) -> None:
    """
    Export s3
    Create file with pyspark. File cannot have custom name with pyspark (create with part-0000-<...>).
    This function divides in two parts.
    Part I - Create file with pyspark
    Part II - Rename file to dataset name. Delete all remaining metadata files.

    :param bucket: Bucket
    :param domain : Domain
    :param data_product : Data product
    :param dataset : Dataset.
    """
    logging.info("==> Starting export s3 <==")

    logging.info("==> PART I: Creating file with pyspark <==")
    spark = (
        SparkSession.builder.appName("exporter")
        .config("spark.sql.caseSensitive", "true")
        .getOrCreate()
    )
    dynamodb_params = get_dynamodb_item(f"{domain}.{data_product}.{dataset}")

    logging.info(f"Dynamo DB parameters: {dynamodb_params}")

    file_format = dynamodb_params.get("file_format")
    platform = dynamodb_params.get("platform")

    s3_dataset_path = f"s3a://{bucket}/{domain}/{data_product}/{dataset}"
    s3_prefix_path = f"{platform}/{domain}/{data_product}/{dataset}"
    s3_export_path = f"file://{BUCKET_EXPORTER}/{s3_prefix_path}"  # diff 3

    df = spark.read.format("delta").load(s3_dataset_path)

    logging.info(f"DF count: {df.count()}")

    df.coalesce(1).write.format(file_format).mode("overwrite").option(
        "header", "true"
    ).save(s3_export_path)

    logging.info("==> PART I: Finished <==")

    logging.info("==> PART II: Renaming file and deleting metadata <==")

    custom_file_name = f"{dataset}.{file_format}"

    # diff 4
    local_export_path = Path(BUCKET_EXPORTER) / s3_prefix_path
    for path in local_export_path.iterdir():
        if path.name.endswith(".csv"):
            path.rename(local_export_path / custom_file_name)
            logging.info(f"File {path.name} renamed to {custom_file_name}")
        else:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            logging.info(f"Deleted file {path.name}!")

    logging.info("==> PART II: Finished <==")

    spark.stop()

    logging.info("==> Finished exporting s3! <==")
