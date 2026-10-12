# TEDUH web image: Next.js built inside the image via Cloud Build, like the API image.
# NEXT_PUBLIC_TEDUH_API is inlined by next.config.ts at build time, so it must be a build arg.
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_TEDUH_API
ENV NEXT_PUBLIC_TEDUH_API=$NEXT_PUBLIC_TEDUH_API

RUN npm run build

ENV NODE_ENV=production \
    PORT=8080

EXPOSE 8080

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "8080"]
