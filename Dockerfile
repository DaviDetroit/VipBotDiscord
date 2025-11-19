FROM python:3.11-slim

WORKDIR /app

# Copia somente o requirements.txt antes de instalar pacotes (melhora cache e evita erros)
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install PyNaCl
RUN pip install requests

RUN apt-get update && apt-get install -y ffmpeg
# Agora copia o restante do código
COPY . .


CMD ["python", "main.py"]
