FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Clean install - remove existing lockfile and node_modules to avoid optional dependency issues
RUN rm -f package-lock.json && \
    rm -rf node_modules && \
    npm install --no-optional --legacy-peer-deps

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

# Start development server (skip type-check to allow dev server to start)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
