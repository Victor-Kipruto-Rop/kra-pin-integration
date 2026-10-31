FROM node:20-alpine
WORKDIR /app
COPY package.json ./
COPY src ./src
ENV NODE_ENV=production PORT=8000
USER node
EXPOSE 8000
CMD ["node","src/server.js"]
