FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=development

# install dependencies
COPY package.json ./
RUN npm install --no-audit --no-fund

# copy source
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
