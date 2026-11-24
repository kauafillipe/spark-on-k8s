# Spark Operator no kind

## Exporter S3 para pasta local

O job adapta `dataflash.exporter.s3`: lê Delta no S3 e grava CSV no computador. A definição do dataset sintético `foundations.staging.study_spark_k8s_exporter` está no repositório `foundations.data.staging`; ela precisa ser implantada e executada na DataFlash antes da exportação. O bucket de origem de produção é `dataflash-gold`. O job local não grava no S3.

A imagem própria usa Spark 3.5.5, Delta 3.2.0, Hadoop AWS 3.3.4, AWS Java SDK 1.12.262 e boto3 1.34.139. `task images:build` usa a CA indicada por `CA_CERT`, se existir. Ela fica instalada na imagem para validar conexões HTTPS também durante a execução.

```sh
saml2aws login --idp-account flash-data --profile flash-data --force
export AWS_PROFILE=flash-data
task cluster
task operator
task images:build
task images:push
task aws:secret
task job:exporter-s3
kubectl --context kind-spark-poc -n spark-jobs get sparkapplications,pods
kubectl --context kind-spark-poc -n spark-jobs logs -f exporter-s3-local-driver
```

O job consulta a tabela DynamoDB `dataflash_export_s3` para obter o formato e a plataforma, como o original. É necessário que exista uma configuração para `foundations.staging.study_spark_k8s_exporter`. Para CSV, o resultado estará em `/tmp/spark-poc-output/<platform>/foundations/staging/study_spark_k8s_exporter/study_spark_k8s_exporter.csv`. Para outro dataset, altere os argumentos em `spark-jobs/exporter-s3.yaml`.

A task `aws:secret` extrai as credenciais temporárias do perfil com AWS CLI e cria o Secret `exporter-s3-aws` no namespace `spark-jobs`, sem salvá-las no repositório. Atualize o login e o Secret antes de cada submissão: credenciais já passadas aos pods não são renovadas automaticamente. Após o término, remova o Secret se não for mais necessário. Para executar novamente, remova antes a SparkApplication concluída: `kubectl --context kind-spark-poc -n spark-jobs delete sparkapplication exporter-s3-local`.

O diretório de saída é montado nos dois workers via `extraMounts`. Se o cluster já existia antes da alteração, será necessário recriá-lo para disponibilizar esse bind; isso apaga os recursos Kubernetes do cluster. No Windows, os arquivos ficam em `spark-poc-output` no diretório temporário do usuário. O arquivo CSV é substituído se o mesmo dataset for exportado novamente.

O Taskfile instala o Spark Operator 2.6.0 pelo chart Helm oficial. O arquivo `infra/spark-operator-values.yaml` configura o namespace de jobs `spark-jobs` e duas réplicas para cada um dos componentes controller e webhook. Não requer Argo CD.

## Pré-requisitos

Instale o Docker Desktop e o [Task](https://taskfile.dev/docs/installation),
e deixe o Docker em execução.
No macOS, instale também o [Homebrew](https://brew.sh/); por exemplo:

```sh
brew install go-task
```

A tarefa `check` instala Helm, kubectl, kind e k9s quando necessário: usa
Homebrew no macOS e Linux, e [winget](https://learn.microsoft.com/windows/package-manager/winget/)
no Windows. O gerenciador correspondente deve estar instalado. A tarefa verifica
o Docker, mas não o instala nem o inicia.

## Executar

Antes de executar os jobs, prepare as imagens privadas e o Secret conforme a
seção abaixo. Depois, na raiz desta POC:

```sh
cd /Users/kauafilipe/Downloads/flash-projects/local-dev/poc_spark_k8s
task up
```

O comando cria o cluster se necessário, aplica o manifesto do namespace
`spark-jobs`, instala o operador e o History Server, aguarda os deployments e
envia o exemplo. Para executar etapas individuais:

```sh
task --list
task check
task cluster
task images:load
task operator
task history
task history-ui
task job
task status
task logs
```

Para excluir o cluster e todos os recursos nele, execute `task cluster:delete`.
Os event logs no diretório local do computador são preservados. Para excluir um
cluster com outro nome, passe `CLUSTER_NAME=outro-nome`.

Use `task up CLUSTER_NAME=outro-nome` para alterar o nome do cluster e passe o
mesmo parâmetro aos comandos posteriores. As mensagens indicam cada etapa; a saída original dos comandos permanece visível.

Ao criar ou reutilizar o cluster, `task cluster` instala nos workers a CA pública
configurada em `CA_CERT`, caso o arquivo exista, e reinicia o containerd nesses
nós. O caminho padrão é o certificado Cloudflare exportado em Downloads neste
ambiente. Para outro caminho, use `task cluster CA_CERT="/caminho/para/ca.pem"`.
O arquivo deve conter um certificado PEM confiável. Se não existir, a etapa é
ignorada. A instalação também pode ser executada separadamente com `task cluster:ca`.

A instalação Helm observa `spark-jobs`. O arquivo `values.yaml` não configura esta instalação.

## Imagens privadas dos jobs

As imagens do Pi e da contagem usam a base oficial Python Spark 3.5.3; a de
contagem acrescenta `spark-jobs/contagem.py`. A imagem do exporter deriva de
`Dockerfile.base-exporter`, baseada na imagem oficial Python Spark 3.5.5, e inclui o job e suas dependências, para testar
uma versão diferente. As tags são publicadas no
mesmo repositório `kaufirs/spark-poc`.

Crie o repositório `spark-poc` como **privado** no Docker Hub e autentique o
Docker. Na raiz desta POC, construa e publique explicitamente:

```sh
docker login
task images:build
task images:push
```

O build local e a publicação são etapas separadas; `task up` não as executa.
Para usar outro usuário, passe `DOCKERHUB_USER=outro-usuario` às duas tarefas e
altere o campo `image` nos manifestos correspondentes em `spark-jobs/`.

Para permitir que o kind baixe imagens privadas, crie o Secret no namespace
`spark-jobs` depois de executar `task cluster` e `task operator`. Use uma senha
ou token do Docker Hub com permissão de leitura:

```sh
read -rs DOCKERHUB_TOKEN
export DOCKERHUB_TOKEN
task dockerhub:secret
unset DOCKERHUB_TOKEN
```

No PowerShell, leia o token de forma oculta e disponibilize-o no ambiente do
processo:

```powershell
$token = Read-Host "Token Docker Hub" -AsSecureString
$env:DOCKERHUB_TOKEN = [System.Net.NetworkCredential]::new("", $token).Password
task dockerhub:secret
Remove-Item Env:DOCKERHUB_TOKEN
Remove-Variable token
```

A leitura oculta o token no terminal. A tarefa monta o Secret em memória e o cria ou atualiza; não é
necessário salvar o token no arquivo. Execute `task history` e
`task job` em seguida, ou use `task up` após criar o Secret. Os manifests usam
`imagePullPolicy: Always` para que uma tag republicada seja consultada novamente.

## Histórico das aplicações Spark

Os jobs `pi.yaml` e `contagem.yaml` gravam event logs em
`/tmp/spark-poc-event-logs` no computador. O kind monta esse diretório em todos
os workers, e o History Server o usa para reconstruir a interface de cada execução.
Depois de executar `task up`, abra outro terminal e rode:

```sh
task history-ui
```

Acesse <http://localhost:18080> enquanto o comando estiver em execução. Cada
nova execução com event logging habilitado aparecerá na lista; pode levar alguns
segundos. O histórico só existe para execuções realizadas depois de ativar os
event logs e permanece enquanto os arquivos locais forem mantidos. No Windows, os logs ficam em `spark-poc-event-logs` dentro do diretório temporário
do usuário (por exemplo, `%TEMP%`). O diretório temporário pode ser limpo pelo
sistema; não é armazenamento permanente.

Se o cluster `spark-poc` já existia antes dessa configuração, é necessário
recriá-lo para adicionar os mounts aos nós. Isso apaga os recursos existentes
no cluster; os event logs no diretório do computador são mantidos:

```sh
task cluster:delete
task up
```

Ao recriar o cluster, gere novamente o kubeconfig do MWAA descrito abaixo.
Se os nós kind não conseguirem baixar imagens por erro de certificado, é
possível baixar a imagem do operador pelo Docker e carregá-la nos workers antes
de executar `task operator` ou repetir `task up`:

```sh
task cluster
task images:load
```

Para carregar também a imagem usada pelo History Server:

```sh
docker pull apache/spark:3.5.3-python3
kind load docker-image --name spark-poc apache/spark:3.5.3-python3
```

Esse procedimento depende de o Docker conseguir acessar os registros e pode
levar alguns minutos para copiar as imagens aos nós. A task carrega a imagem do
operador apenas nos workers; se o operador for configurado para executar no
control plane, a imagem também precisará estar disponível nele. Para outro cluster, passe
`CLUSTER_NAME=outro-nome` à task e use o mesmo nome no comando `kind load`.

## DAGs no MWAA local

Os workers kind usam labels de teste `tier=standard` e
`tier=optimized`. Os jobs pi e exporter selecionam `standard`; pi com
TTL e contagem selecionam `optimized`. Os tiers testam apenas o posicionamento,
pois os workers compartilham os recursos da máquina local. Em um cluster já
existente, aplique as labels sem recriá-lo (confirme os nomes com `kubectl get
nodes`):

```sh
kubectl --context kind-spark-poc label node spark-poc-worker tier=standard --overwrite
kubectl --context kind-spark-poc label node spark-poc-worker2 tier=optimized --overwrite
kubectl --context kind-spark-poc get nodes -L tier
kubectl --context kind-spark-poc -n spark-jobs get pods -o wide
```

Clusters novos recebem as labels pela configuração kind. Sem a label no nó,
os pods que a selecionam permanecerão pendentes.

As DAGs `spark_pi_kind`, `spark_pi_ttl_kind`, `spark_contagem_kind` e
`spark_exporter_s3_kind` são disparadas manualmente no Airflow. Para o exporter,
configure o dataset, a imagem e o Secret AWS conforme a seção anterior antes de
disparar a DAG. Com o cluster kind criado, prepare o kubeconfig para o container do
MWAA local e inicie ou recrie o runner a partir da raiz dele:

```sh
cd /Users/kauafilipe/Downloads/flash-projects/aws-mwaa-local-runner
sh prepare-kind-kubeconfig.sh
./mwaa-local-env start
```

Se o runner já estiver em execução, pare-o antes e inicie-o novamente para
aplicar os volumes e instalar o provider Kubernetes declarado nos requirements.
Execute o script novamente após recriar o cluster. Para outro nome de cluster,
use `CLUSTER_NAME=outro-nome sh prepare-kind-kubeconfig.sh`.

Na interface do Airflow, em **Admin → Connections**, crie a connection:

- **Connection Id:** `kubernetes_kind`
- **Connection Type:** `Kubernetes Cluster Connection`
- **In cluster configuration:** desativado
- **Kube config path:** `/usr/local/airflow/.local-kube/config`
- **Namespace:** `spark-jobs`

O kubeconfig gerado em `.local-kube/` contém credenciais de administrador do
kind: mantenha-o local. O script usa `host.docker.internal`, para Docker Desktop
no macOS. A imagem de contagem inclui `contagem.py` no caminho indicado por
`mainApplicationFile`.

O job de contagem usa alocação dinâmica: começa com um executor e pode solicitar
até quatro, conforme a demanda e os recursos disponíveis no cluster. O shuffle
tracking ajuda a preservar executores com dados de shuffle ainda necessários.
Jobs curtos podem terminar antes de ser possível observar a expansão ou redução.

## Observar a Spark UI e a retenção

Depois de alterar `contagem.py`, reconstrua e publique a imagem de contagem
com `task images:build` e `task images:push`, conforme a seção de imagens.
O código é incluído na imagem durante o build. Dispare a DAG
`spark_contagem_kind` ou crie a aplicação diretamente:

```sh
kubectl --context kind-spark-poc create -f spark-jobs/contagem.yaml
kubectl --context kind-spark-poc -n spark-jobs get pods -w
```

Em outro terminal, enquanto o pod do driver estiver em execução, substitua o
nome abaixo pelo nome exibido no comando anterior:

```sh
kubectl --context kind-spark-poc -n spark-jobs port-forward pod/<nome-do-driver> 4040:4040
```

Acesse <http://localhost:4040>. Após o processamento, o driver espera 120
segundos antes de encerrar, dando tempo para explorar a UI. A espera mantém o
driver ativo, mas não garante que a expansão ou a redução dos executors seja
visível. Após o término, consulte a execução no History Server seguindo a
seção de histórico acima. Para outro cluster, substitua `kind-spark-poc` pelo
contexto correspondente. A aplicação de contagem tem nome fixo: remova uma
execução anterior antes de criá-la novamente diretamente com `kubectl create`.

Para comparar a retenção, crie as duas variantes do Pi e acompanhe seus estados:

```sh
kubectl --context kind-spark-poc create -f spark-jobs/pi.yaml
kubectl --context kind-spark-poc create -f spark-jobs/pi-ttl.yaml
kubectl --context kind-spark-poc -n spark-jobs get sparkapplications,pods -w
```

A variante `spark-pi-ttl-` define `timeToLiveSeconds: 60`: depois de terminar,
o Operator remove a SparkApplication após aproximadamente 60 segundos, sujeito
ao intervalo de reconciliação. A variante `spark-pi-` não define TTL e não é
removida por esse mecanismo. Observe também os pods: o Spark normalmente remove
os executors ao término; o driver concluído pode permanecer até uma limpeza.
O TTL da aplicação não apaga os event logs, que têm ciclo de vida próprio.
Interrompa o acompanhamento com Ctrl+C.
