FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

# Start development server
# Run type-check before starting dev server
# If type-check fails, the container will exit
CMD ["sh", "-c", "npm run type-check && npm run dev -- --host 0.0.0.0"]
