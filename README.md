# ProjetoVipBot

Bot de Discord para gerenciamento de VIP por reação, avisos automáticos de expiração e acompanhamento de jogos de futebol em tempo real via API — com persistência em MySQL.

## Sumário
- Visão Geral
- Funcionalidades
- Pré‑requisitos
- Instalação
- Configuração (.env)
- Banco de Dados (MySQL)
- Execução
- Permissões do Discord
- Fluxos e Agendamentos
- Sistema de Apostas
- Troubleshooting
- Contribuição
- Licença

## Visão Geral
O ProjetoVipBot automatiza a atribuição de cargos VIP ao reagir em uma mensagem, envia avisos de expiração, e acompanha partidas do Brasileirão com notificações de gols e abertura/encerramento de apostas — tudo integrado ao MySQL para registro de VIPs, apostas, histórico e pontuação.

## Funcionalidades
- 👑 VIP por reação: mensagem com embed + reação; ao reagir, o usuário recebe o cargo VIP e o registro é salvo em `vips`.
- ⏰ Aviso de expiração: após 23 dias, envia DM para o usuário e aviso em canal público configurado.
- ⚽ Acompanhamento de jogos: consulta API de futebol a cada 5 minutos; notifica gols com minuto, abre/encerra apostas, aplica pontuação e envia resultado final.
- 🎰 Apostas por reação: casa/fora/empate; suporta modo clown (multiplica pontos positivos/negativos) e preços configuráveis (VIP Jinxed, ticket de reaposta, etc.).
- 💾 MySQL: armazena VIPs, apostas, histórico de jogos e pontuação de usuários.

## Pré‑requisitos
- Python 3.10+
- MySQL 8+ (ou compatível)
- Token de bot do Discord
- Token da API de futebol
- Permissões e Intents configuradas no Discord Developer Portal