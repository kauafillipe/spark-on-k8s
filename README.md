# Spark Operator no kind

O Taskfile instala o Spark Operator 2.6.0 pelo chart Helm oficial e configura as permissões para jobs no namespace `spark-jobs`. Não requer Argo CD.

## Pré-requisitos

Instale o Docker Desktop e o [Task](https://taskfile.dev/docs/installation),
e deixe o Docker em execução.
No macOS, instale também o [Homebrew](https://brew.sh/); por exemplo:

```sh
brew install go-task
```

A tarefa `check` instala Helm, kubectl, kind e k9s via Homebrew quando necessário.
No Windows, instale Helm, kubectl, kind e k9s previamente e confira se essas
ferramentas estão no PATH. A tarefa verifica o Docker, mas não o instala
nem o inicia.

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
task operator
task history
task history-ui
task job
task status
task logs
```

Use `task up CLUSTER_NAME=outro-nome` para alterar o nome do cluster e passe o
mesmo parâmetro aos comandos posteriores. As mensagens indicam cada etapa; a saída original dos comandos permanece visível.

A instalação Helm observa `spark-jobs`. O arquivo `values.yaml` não configura esta instalação.

## Imagens privadas dos jobs

Os Dockerfiles em `images/` usam Spark 3.5.3: a imagem base deriva da imagem
oficial Python; a imagem do Pi usa o exemplo já presente na base; e a de
contagem acrescenta `spark-jobs/contagem.py`. As três tags são publicadas no
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
altere o campo `image` nos dois arquivos em `spark-jobs/`.

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
kind delete cluster --name spark-poc
task up
```

Ao recriar o cluster, gere novamente o kubeconfig do MWAA descrito abaixo.
Se os nós kind não conseguirem baixar imagens por erro de certificado, é
possível baixá-las pelo Docker e carregá-las no cluster antes de repetir
`task up`:

```sh
docker pull ghcr.io/kubeflow/spark-operator/controller:2.6.0
docker pull apache/spark:3.5.3-python3
kind load docker-image --name spark-poc ghcr.io/kubeflow/spark-operator/controller:2.6.0 apache/spark:3.5.3-python3
```

Esse procedimento depende de o Docker conseguir acessar os registros e pode
levar alguns minutos para copiar as imagens aos nós.

## DAGs no MWAA local

As DAGs `spark_pi_kind` e `spark_contagem_kind` são disparadas manualmente no
Airflow. Com o cluster kind criado, prepare o kubeconfig para o container do
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
