# Minuta de solicitação de dados ao TSE

> **Arquivada, não enviada.** O recorte vigente avalia somente 2018/2022/2026; este pedido para 2010/2014 fica como material para uma possível ampliação e não é necessário para executar a [metodologia atual](metodologia.md).

**Finalidade:** pesquisa acadêmica comparando métodos de projeção eleitoral durante a apuração. Texto preparado para revisão e envio pelo responsável pelo trabalho.

Solicitamos, para as eleições presidenciais de **2010 e 2014, segundo turno, Brasil e exterior**, os registros disponíveis que permitam reconstruir a evolução temporal da apuração e totalização.

A necessidade principal é identificar a ordem das seções contabilizadas, pois resultados finais agregados e parciais apenas nacionais não permitem reproduzir os dados observados por cada estimador ao longo da noite.

Se disponíveis, solicitamos:

1. **Registros por seção**, com UF, código eleitoral do município, zona, seção, eleição, turno, cargo e horários de recebimento do BU e de primeira totalização parcial, com significado e fuso de cada campo. Campos equivalentes a `DT_RECEBIMENTO_BU_HOR_TSE` e `DT_PRIM_TOT_PARCIAL_HOR_TSE`, disponíveis no detalhe de 2018, atenderiam parte da necessidade.
2. **Eventos de correção ou retotalização**, contendo identificação da seção, horário, votos e contagens alterados, quando houver. Se o horário disponível se referir apenas à última versão, solicitamos que isso seja informado.
3. **Histórico de parciais acumuladas**, nacional e, quando possível, por UF, município ou zona, com horários, votos dos candidatos, seções contabilizadas e denominador de seções.
4. **Leiaute e documentação**, incluindo seções agregadas, não instaladas, anuladas, trânsito e exterior; distinção entre recebimento, processamento, totalização e disponibilização pública.

O PDF “Evolução da totalização para Presidente no 2º turno de 2014” já fornece 333 observações nacionais de horário e votos, mas não contém contagens ou identificação de seções. Os arquivos de detalhe por seção consultados de 2010 e 2014 não contêm os timestamps presentes na publicação de 2018.

Preferimos CSV, JSON ou outro formato estruturado. Se não houver extração pronta, registros de eventos ou logs administrativos equivalentes podem atender à pesquisa, acompanhados do leiaute. Não são necessários dados pessoais de eleitores nem identificadores individuais de voto.

Caso parte desses dados não esteja preservada ou não possa ser fornecida, solicitamos informar quais anos, turnos, granularidades e campos estão disponíveis, assim como a limitação correspondente.
