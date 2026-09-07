FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Passed in from docker-compose so the built frontend knows where
# the backend actually lives - fixes the hardcoded localhost:8000 bug.
ARG VITE_WS_URL=ws://localhost:8000/ws
ENV VITE_WS_URL=$VITE_WS_URL

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
