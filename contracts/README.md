# Contrato experimental de divisão

Este projeto contém um contrato de pagamento nativo com divisão imediata 50/50. Ele **não localiza moedas, não recupera ativos de carteiras e não identifica titulares**.

## Requisitos

- Node.js LTS
- npm

## Compilar e testar

Na pasta `contracts`:

```bash
npm install
npm test
npm run compile
```

## Deploy

Ainda não existe script de deploy nem autorização para mainnet. Antes de qualquer implantação real, exigir:
1. testes locais e em testnet;
2. revisão independente do Solidity e das dependências;
3. revisão jurídica do contrato de prestação de serviços;
4. validação dos endereços beneficiários e do fluxo de consentimento;
5. aprovação expressa do responsável pelo projeto.

Não enviar fundos reais para este contrato experimental.
