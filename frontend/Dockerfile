# Build Stage
FROM node:20-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production Stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
# Update nginx config to listen on 3000 for consistency if needed, 
# but easiest is to just map 3000:80 in compose or let nginx default 80.
# Let's keep it 3000:3000 mapping in compose.
CMD ["nginx", "-g", "daemon off;"]
