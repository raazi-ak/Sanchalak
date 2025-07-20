import express from 'express';
import { ApolloServer } from 'apollo-server-express';
import { graphqlUploadExpress } from 'graphql-upload';
import cors from 'cors';
import path from 'path';
import dotenv from 'dotenv';
import { typeDefs } from './graphql/schema';
import { resolvers } from './graphql/resolvers';
import { logger } from './services/logger';

// Load environment variables
dotenv.config();

async function startServer() {
  const app = express();
  const PORT = process.env.PORT || 3001;

  logger.info('Starting Sanchalak Backend Server...');
  logger.debug(`Environment: ${process.env.NODE_ENV}`);
  logger.debug(`Log Level: ${process.env.LOG_LEVEL || 'info'}`);

  // CORS configuration
  app.use(cors({
    origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
    credentials: true
  }));

  logger.debug(`CORS configured for origin: ${process.env.CORS_ORIGIN || 'http://localhost:3000'}`);

  // Serve static files (audio files)
  app.use('/audio', express.static(path.join(process.cwd(), 'public', 'audio')));

  // GraphQL upload middleware
  app.use('/graphql', graphqlUploadExpress({ maxFileSize: 25000000, maxFiles: 1 }));

  // Create Apollo Server
  const server = new ApolloServer({
    typeDefs,
    resolvers,
    context: ({ req }) => ({
      req
    }),
    uploads: false, // We handle uploads with graphqlUploadExpress
    introspection: process.env.NODE_ENV !== 'production',
    playground: process.env.NODE_ENV !== 'production'
  });

  await server.start();
  server.applyMiddleware({ app, path: '/graphql' });

  // Health check endpoint
  app.get('/health', (req, res) => {
    res.json({ 
      status: 'healthy', 
      timestamp: new Date().toISOString(),
      graphql: server.graphqlPath 
    });
  });

  // Start server
  app.listen(PORT, () => {
    logger.info(`🚀 Server ready at http://localhost:${PORT}`);
    logger.info(`📊 GraphQL endpoint: http://localhost:${PORT}${server.graphqlPath}`);
    logger.info(`🎵 Audio files served at: http://localhost:${PORT}/audio`);
    logger.info(`🌾 Sanchalak Backend is ready to help farmers!`);
  });
}

// Handle graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received. Shutting down gracefully...');
  process.exit(0);
});

process.on('SIGINT', () => {
  logger.info('SIGINT received. Shutting down gracefully...');
  process.exit(0);
});

// Start the server
startServer().catch((error) => {
  logger.error('Failed to start server:', error);
  process.exit(1);
});
