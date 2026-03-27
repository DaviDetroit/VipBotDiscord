# 👑⚽ ProjetoVipBot

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Discord.py](https://img.shields.io/badge/Discord.py-2.x-5865F2?logo=discord&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8%2B-4479A1?logo=mysql&logoColor=white)
![API-Football](https://img.shields.io/badge/API--Football-RapidAPI-00A8E1?logo=rapidapi&logoColor=white)![License](https://img.shields.io/badge/License-MIT-blue)

> **Bot de Discord para gerenciamento de VIP, apostas e jogos de futebol em tempo real com integração MySQL**

---

## 📑 Sumário
- [✨ Visão Geral](#-visão-geral)
- [🚀 Funcionalidades](#-funcionalidades)
- [📋 Pré-requisitos](#-pré-requisitos)
- [⚙️ Instalação](#️-instalação)
- [🔐 Configuração (.env)](#-configuração-env)
- [🗄️ Banco de Dados](#️-banco-de-dados)
- [▶️ Execução](#️-execução)
- [🛡️ Permissões do Discord](#️-permissões-do-discord)
- [🔄 Fluxos e Agendamentos](#-fluxos-e-agendamentos)
- [🎰 Sistema de Apostas](#-sistema-de-apostas)
- [🐛 Troubleshooting](#-troubleshooting)
- [🤝 Contribuição](#-contribuição)
- [📄 Licença](#-licença)

---

## ✨ Visão Geral

O **ProjetoVipBot** automatiza completamente o gerenciamento de VIPs e eventos dentro do Discord, incluindo:

- 👑 Sistema VIP por reação  
- ⏳ Controle automático de expiração  
- ⚽ Monitoramento de jogos em tempo real  
- 🎰 Sistema de apostas interativo  
- 💾 Armazenamento persistente com MySQL  

---

## 🚀 Funcionalidades

### 👑 VIP por Reação
- Usuário reage com 👑 em uma mensagem embed  
- Cargo VIP é atribuído automaticamente  
- Registro salvo no banco (`vips`)  

---

### ⏰ Expiração Automática
- VIP dura **23 dias**  
- Sistema envia:
  - 📩 Mensagem privada (DM)  
  - 📢 Aviso em canal público  
- Remoção automática do cargo  

---

### ⚽ Jogos em Tempo Real
- Atualização a cada **5 minutos**  
- Detecta:
  - 🟢 Início de partida  
  - ⚽ Gols com minuto  
  - 🔴 Fim do jogo  
- Notificações automáticas no Discord  

---

### 🎰 Sistema de Apostas
- Apostas por reação:
  - 🏠 Casa  
  - 🤝 Empate  
  - ✈️ Fora  
- Recursos:
  - 💰 Sistema de pontuação  
  - 🤡 Modo Clown (multiplicador de risco)  
  - 🎟️ Tickets especiais (reaposta, VIP bônus, etc.)  

---

### 💾 Banco de Dados
- MySQL integrado  
- Armazena:
  - VIPs  
  - Apostas  
  - Histórico de jogos  
  - Pontuação de usuários  

---

## 📋 Pré-requisitos

- Python **3.10+**
- MySQL **8+**
- Conta no Discord Developer Portal
- Token de bot do Discord
- API de futebol (ex: API-Football)

---

## ⚙️ Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/ProjetoVipBot.git

# Acesse a pasta
cd ProjetoVipBot

# Crie ambiente virtual (opcional)
python -m venv venv

# Ative o ambiente
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt