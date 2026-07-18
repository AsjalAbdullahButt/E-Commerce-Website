# Multi-stage: build minified static assets with Node, then serve them with the same plain
# python:3.12-slim + http.server the non-Docker dev workflow already uses (README's
# `python -m http.server 5500 --directory frontend`) — just pointed at the built dist/ instead
# of the raw source tree. Dev (outside Docker) keeps serving unminified frontend/ directly.
FROM node:20-slim AS build
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM python:3.12-slim
WORKDIR /frontend
COPY --from=build /frontend/dist ./
EXPOSE 5500
CMD ["python", "-m", "http.server", "5500"]
