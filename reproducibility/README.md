# Reprodução e proveniência

`tse-manifests/` preserva os cinco catálogos e os manifestos de 65 ZIPs oficiais necessários aos três anos: 2018/2022/2026. Os dados brutos ficam fora do Git. `scripts/dataset_snapshot.py seed` copia esses metadados para um diretório novo; `verify` confere tamanho e SHA-256 dos arquivos baixados. Os catálogos congelam as URLs, e a conferência de hash detecta uma alteração posterior da fonte.

`cpu-validation.json` registra a execução com o wheel oficial Torch 2.12.0+cpu: suíte de testes, grade completa e comparação com as projeções originais. O wheel teve seu SHA-256 conferido. A validação usou um container CPU isolado baseado na imagem local, com o Torch CPU temporariamente instalado e as dependências de análise fixadas. A receita `Dockerfile.cpu` usa uma base Python pública com digest verificado; seu build completo não foi executado nesta máquina para preservar espaço em disco. Não se pressupõe acesso de outra pessoa à imagem GPU local.

A reprodução numérica permite diferenças até 1e-10 na proporção de A; a validação registrada obteve diferença zero nos três anos. Tempos e metadados não são comparados byte a byte. Nenhum dado de entrada foi modificado durante a validação; o SSD ficou montado somente para leitura, sem dispositivos NVIDIA expostos.
