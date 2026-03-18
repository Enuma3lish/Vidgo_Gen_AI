FROM node:20-alpine

WORKDIR /app

# Install libc compatibility layer needed by native modules on Alpine ARM64
RUN apk add --no-cache libc6-compat

# Copy package files
COPY package*.json ./

# Clean install - fresh lockfile to resolve correct platform-specific dependencies
RUN rm -f package-lock.json && \
    rm -rf node_modules && \
    npm install --legacy-peer-deps

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

# Start development server (skip type-check to allow dev server to start)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
