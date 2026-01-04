// Portfolio Mode - Multi-Cluster Visualization
// Displays top 5 holdings as separate clusters + background cluster

#ifndef PORTFOLIO_MODE_H
#define PORTFOLIO_MODE_H

#include <Arduino.h>

// Maximum number of clusters (5 top holdings + 1 background)
const int MAX_CLUSTERS = 6;

// Cluster data structure
struct ClusterData {
  int clusterID;        // 0 = background, 1-5 = top holdings
  int pixels;           // Number of pixels for this cluster
  uint8_t brightness;   // Brightness level (100-220)
  int clustering;       // Clustering strength (1-10)
  int speed;            // Animation speed in ms
  char symbol[10];      // Security symbol (empty for background)
};

// Portfolio mode state
extern bool inPortfolioMode;
extern ClusterData clusters[MAX_CLUSTERS];
extern int numClusters;
extern uint8_t pixelClusterID[8][13];  // Which cluster each pixel belongs to

// Portfolio mode functions
void setPortfolioMode(const char* clustersJSON);
void updatePortfolioPattern();
void parseClusterData(const char* json);
int countClusterNeighbors(uint8_t x, uint8_t y, int targetClusterID);

#endif
