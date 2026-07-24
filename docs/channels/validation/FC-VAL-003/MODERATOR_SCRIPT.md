# Moderator script

Protocol version: `fc-val-003-v1`.

Text labeled **say** must be read verbatim. Text labeled **do not say** is a
moderator guardrail. Do not explain channels before Stage A is scored.

## Consent and eligibility

**Say**

> Estamos avaliando se uma descrição de produto é compreensível, não você. A
> sessão dura cerca de 15 minutos. Não use nem mostre uma wallet real, saldo,
> transação, link privado, chave ou seed phrase. Podemos interromper ou excluir
> suas respostas a qualquer momento. Suas respostas públicas serão apenas
> agregadas e sem identificação. Você concorda em participar?

Record `consent_obtained=true` privately. If the answer is no, stop. Obtain any
recording consent separately; participation must not require recording.

Ask the eligibility questions as yes/no:

1. Você tem 18 anos ou mais?
2. Enviou ou recebeu stablecoin pelo menos duas vezes nos últimos seis meses?
3. Já usou uma wallet autocustodial?
4. Trabalha ou colaborou diretamente com Foundry Pay ou Solana-Agent?
5. Já leu documentação sobre Foundry Channels?
6. Enviou stablecoins repetidamente para a mesma pessoa?
7. Já recebeu stablecoins em uma wallet própria?

Exclude when questions 1–3 are not all yes, or 4–5 are yes.

## Neutral introduction

**Say**

> Vou mostrar uma frase durante 30 segundos. Depois vou escondê-la e pedir que
> você explique o que entendeu. Não existe resposta que você precise adivinhar.
> Se algo não estiver claro, diga exatamente isso.

**Do not say**

- “É como um canal de pagamento.”
- “O link é reutilizável.”
- “Os valores não somam.”
- “Os fundos ficam em um programa.”

## Stage A — unaided 30-second comprehension

Show only:

> **Abra um canal. Compartilhe um link. Envie quantas vezes quiser.**

Start a 30-second timer. Do not answer questions beyond: “Use apenas o que a
frase comunica para você.” Hide the phrase at 30 seconds.

Ask in order:

1. **Com suas palavras, o que você acha que esse produto permite fazer?**
2. **O que significa “canal” para você aqui?**
3. **O que você acha que acontece com o link depois do primeiro envio?**
4. **Quem recebe e onde você imagina que o valor chega?**
5. **Quem você imagina que controla ou guarda o dinheiro enquanto ele ainda não
   foi recebido?**
6. **O que está faltando na frase para você decidir se usaria isso?**

Use only neutral probes:

- “Pode explicar um pouco mais?”
- “O que fez você pensar isso?”
- “Existe outra interpretação possível?”

Do not correct answers. Lock Stage A scoring before continuing.

## Stage B — factual model comprehension

Show and read:

> Alice financia um canal com 100 USDC. O canal mantém os fundos em um programa
> Solana, não em uma conta controlada pelo serviço Foundry Pay. Alice assina
> atualizações cumulativas: primeiro o total autorizado é 10, depois 25, depois
> 40. Cada atualização válida substitui o total anterior; os três números não
> são somados. A assinatura emite a atualização; a aceitação pelo programa
> Solana a ativa como direito liquidável. Bob recebe um link protegido, vincula
> a própria wallet e pode liquidar o valor ativado. Se Alice pedir o fechamento,
> Bob ainda deve ter uma janela explícita para apresentar a última atualização
> assinada antes do prazo. Depois do prazo, regras de expiração e reembolso se
> aplicam. O link pode ser reutilizado para atualizações futuras e deve ser
> tratado como informação sensível.

Ask without arithmetic hints:

1. Qual é o total autorizado depois de `10 → 25 → 40`?
2. Se Bob já liquidou 15, quanto ainda pode liquidar sob o total 40?
3. Se Bob liquidar os 40, quanto do financiamento inicial permanece no canal?
4. Qual a diferença entre:
   - financiado;
   - autorizado;
   - recebido/liquidado;
   - remanescente?
5. O voucher de 10 pode ser somado ao de 40 para receber 50? Por quê?
6. O serviço Foundry Pay pode inventar um voucher ou aumentar o total sozinho?
7. O que Bob deve fazer com o link protegido?
8. O que deveria acontecer se o resultado de uma operação for desconhecido?
9. Qual é a diferença entre uma atualização assinada e uma atualização ativada?
10. Se Alice pedir fechamento, o voucher já assinado por ela desaparece
    imediatamente?

Expected accounting:

- authorized: 40;
- liquidatable after 15 settled: 25;
- remaining funded capacity after 40 settled: 60;
- old vouchers create no additive right;
- unknown result requires status/recovery, not a blind second payment.
- signature issues the update; program acceptance activates the right;
- closing preserves a deadline to present the latest eligible signed update.

## Comparison and intent

Ask last so preference does not contaminate comprehension:

1. Como isso difere de pedir o endereço da wallet e fazer uma transferência
   comum?
2. Em qual situação, se alguma, um link reutilizável seria útil para você?
3. O que impediria você de usar?
4. Numa escala de 1 a 5, quão clara foi a frase inicial?
5. Numa escala de 1 a 5, quão provável seria reutilizar esse canal numa relação
   recorrente? Por quê?

Intent is not adoption. Report these answers as stated preference only.

## Debrief

**Say**

> Obrigado. Esta foi uma pesquisa sobre uma proposta em desenvolvimento. Nenhum
> canal real foi aberto e nenhum pagamento ocorreu. Não envie posteriormente
> wallets, chaves, seed phrases ou links privados. Se desejar retirar sua
> participação, use o contato de pesquisa fornecido no consentimento.
