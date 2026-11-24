import time

from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.appName("contagem-distribuida").getOrCreate()

dados = spark.range(0, 20_000_000, numPartitions=64)
resultado = dados.groupBy((F.col("id") % 1000).alias("grupo")).count()
resultado.orderBy("grupo").show(20)

# Mantém a Spark UI disponível após o processamento para a demonstração.
print("Processamento concluído; Spark UI disponível por mais 120 segundos.", flush=True)
time.sleep(120)
spark.stop()
