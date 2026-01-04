// Portfolio Mode - Multi-Cluster Visualization
// Implements organic clustering for multiple security clusters

#include "portfolio_mode.h"
#include <Arduino.h>
#include <string.h>

// Portfolio mode state
bool inPortfolioMode = false;
ClusterData clusters[MAX_CLUSTERS];
int numClusters = 0;
uint8_t pixelClusterID[8][13];  // Which cluster each pixel belongs to

// Pixel tracking array - same approach as single-cluster mode
// First N pixels belong to clusters, organized by cluster membership
extern uint8_t pixelIndices[104];  // From main sketch

// Matrix dimensions
const int MATRIX_WIDTH = 13;
const int MATRIX_HEIGHT = 8;
const int TOTAL_PIXELS = 104;

// Animation timing - per-cluster animation speeds
unsigned long lastUpdateTime[MAX_CLUSTERS] = {0};

// Helper: Simple JSON value extraction (minimal parser for Arduino)
// Extracts integer value for a key like "cluster_id":1
int extractInt(const char* json, const char* key) {
  char searchStr[32];
  snprintf(searchStr, sizeof(searchStr), "\"%s\":", key);
  const char* pos = strstr(json, searchStr);
  if (pos) {
    pos += strlen(searchStr);
    while (*pos == ' ') pos++;  // Skip whitespace
    return atoi(pos);
  }
  return 0;
}

// Helper: Extract string value for a key like "symbol":"AAPL"
void extractString(const char* json, const char* key, char* output, int maxLen) {
  char searchStr[32];
  snprintf(searchStr, sizeof(searchStr), "\"%s\":\"", key);
  const char* pos = strstr(json, searchStr);
  if (pos) {
    pos += strlen(searchStr);
    int i = 0;
    while (*pos && *pos != '"' && i < maxLen - 1) {
      output[i++] = *pos++;
    }
    output[i] = '\0';
  } else {
    output[0] = '\0';
  }
}

// Parse cluster data from JSON array
// Expected format: [{"cluster_id":1,"pixels":20,"brightness":180,"clustering":3,"speed":100,"symbol":"AAPL"},...]
void parseClusterData(const char* json) {
  numClusters = 0;

  // Find start of array
  const char* pos = strchr(json, '[');
  if (!pos) return;
  pos++;

  // Parse each cluster object
  while (numClusters < MAX_CLUSTERS) {
    // Find next object
    const char* objStart = strchr(pos, '{');
    if (!objStart) break;

    const char* objEnd = strchr(objStart, '}');
    if (!objEnd) break;

    // Extract cluster object (null-terminate temporarily)
    int objLen = objEnd - objStart + 1;
    char objBuf[256];
    if (objLen >= sizeof(objBuf)) break;
    strncpy(objBuf, objStart, objLen);
    objBuf[objLen] = '\0';

    // Parse cluster fields
    ClusterData& cluster = clusters[numClusters];
    cluster.clusterID = extractInt(objBuf, "cluster_id");
    cluster.pixels = extractInt(objBuf, "pixels");
    cluster.brightness = (uint8_t)extractInt(objBuf, "brightness");
    cluster.clustering = extractInt(objBuf, "clustering");
    cluster.speed = extractInt(objBuf, "speed");
    extractString(objBuf, "symbol", cluster.symbol, sizeof(cluster.symbol));

    // Constrain values
    cluster.pixels = constrain(cluster.pixels, 0, TOTAL_PIXELS);
    cluster.brightness = constrain(cluster.brightness, 80, 220);
    cluster.clustering = constrain(cluster.clustering, 1, 10);
    cluster.speed = constrain(cluster.speed, 10, 500);

    numClusters++;
    pos = objEnd + 1;
  }
}

// Set portfolio mode with cluster configuration
void setPortfolioMode(const char* clustersJSON) {
  // Parse cluster data
  parseClusterData(clustersJSON);

  if (numClusters == 0) {
    inPortfolioMode = false;
    return;
  }

  // Initialize pixel-to-cluster mapping
  memset(pixelClusterID, 0, sizeof(pixelClusterID));

  // Allocate pixels to clusters sequentially
  // First cluster.pixels go to cluster 0, next cluster.pixels to cluster 1, etc.
  int pixelIdx = 0;
  for (int c = 0; c < numClusters; c++) {
    int clusterPixels = clusters[c].pixels;
    for (int p = 0; p < clusterPixels && pixelIdx < TOTAL_PIXELS; p++) {
      uint8_t pos = pixelIndices[pixelIdx];
      uint8_t x = pos % MATRIX_WIDTH;
      uint8_t y = pos / MATRIX_WIDTH;
      pixelClusterID[y][x] = clusters[c].clusterID;
      pixelIdx++;
    }
  }

  // Initialize animation timers
  for (int i = 0; i < MAX_CLUSTERS; i++) {
    lastUpdateTime[i] = 0;
  }

  inPortfolioMode = true;
}

// Count neighbors belonging to target cluster (for intra-cluster attraction)
int countClusterNeighbors(uint8_t x, uint8_t y, int targetClusterID) {
  int count = 0;
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) continue;  // Skip center pixel
      int nx = x + dx;
      int ny = y + dy;
      if (nx >= 0 && nx < MATRIX_WIDTH && ny >= 0 && ny < MATRIX_HEIGHT) {
        if (pixelClusterID[ny][nx] == targetClusterID) {
          count++;
        }
      }
    }
  }
  return count;
}

// Count neighbors belonging to DIFFERENT clusters (for inter-cluster repulsion)
int countOtherClusterNeighbors(uint8_t x, uint8_t y, int ownClusterID) {
  int count = 0;
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      if (dx == 0 && dy == 0) continue;  // Skip center pixel
      int nx = x + dx;
      int ny = y + dy;
      if (nx >= 0 && nx < MATRIX_WIDTH && ny >= 0 && ny < MATRIX_HEIGHT) {
        if (pixelClusterID[ny][nx] != 0 && pixelClusterID[ny][nx] != ownClusterID) {
          count++;
        }
      }
    }
  }
  return count;
}

// Update portfolio pattern with multi-cluster organic animation
void updatePortfolioPattern() {
  unsigned long currentTime = millis();

  // Process each cluster independently
  int pixelOffset = 0;
  for (int c = 0; c < numClusters; c++) {
    ClusterData& cluster = clusters[c];

    // Check if enough time has passed for this cluster's animation speed
    if (currentTime - lastUpdateTime[c] < (unsigned long)cluster.speed) {
      pixelOffset += cluster.pixels;
      continue;
    }
    lastUpdateTime[c] = currentTime;

    // Skip if no pixels in this cluster
    if (cluster.pixels == 0) continue;

    // Multi-cluster organic algorithm:
    // 1. Find isolated pixel from THIS cluster (few same-cluster neighbors, many other-cluster neighbors)
    // 2. Find position with many same-cluster neighbors and few other-cluster neighbors
    // 3. Swap to increase clustering

    int bestIsolatedIdx = pixelOffset + random(cluster.pixels);  // Fallback
    int worstScore = -100;  // Lower score = more isolated

    // Sample clustering_strength candidates to find most isolated pixel
    for (int i = 0; i < cluster.clustering; i++) {
      int idx = pixelOffset + random(cluster.pixels);
      uint8_t pos = pixelIndices[idx];
      uint8_t x = pos % MATRIX_WIDTH;
      uint8_t y = pos / MATRIX_WIDTH;

      // Score: prefer pixels with few same-cluster neighbors and many other-cluster neighbors
      int sameNeighbors = countClusterNeighbors(x, y, cluster.clusterID);
      int otherNeighbors = countOtherClusterNeighbors(x, y, cluster.clusterID);
      int score = sameNeighbors - otherNeighbors;  // Lower = more isolated

      if (score > worstScore) {
        worstScore = score;
        bestIsolatedIdx = idx;
      }
    }

    // Find best target position (within this cluster's pixels)
    int bestTargetIdx = pixelOffset + random(cluster.pixels);  // Fallback
    int bestScore = -100;  // Higher score = better clustering

    for (int i = 0; i < cluster.clustering; i++) {
      int idx = pixelOffset + random(cluster.pixels);
      uint8_t pos = pixelIndices[idx];
      uint8_t x = pos % MATRIX_WIDTH;
      uint8_t y = pos / MATRIX_WIDTH;

      // Score: prefer positions with many same-cluster neighbors and few other-cluster neighbors
      int sameNeighbors = countClusterNeighbors(x, y, cluster.clusterID);
      int otherNeighbors = countOtherClusterNeighbors(x, y, cluster.clusterID);
      int score = sameNeighbors - otherNeighbors;  // Higher = better clustering

      if (score > bestScore) {
        bestScore = score;
        bestTargetIdx = idx;
      }
    }

    // Swap isolated pixel with better-clustered position
    if (bestIsolatedIdx != bestTargetIdx) {
      uint8_t temp = pixelIndices[bestIsolatedIdx];
      pixelIndices[bestIsolatedIdx] = pixelIndices[bestTargetIdx];
      pixelIndices[bestTargetIdx] = temp;

      // Update cluster ID mapping
      uint8_t pos1 = pixelIndices[bestIsolatedIdx];
      uint8_t pos2 = pixelIndices[bestTargetIdx];
      uint8_t x1 = pos1 % MATRIX_WIDTH;
      uint8_t y1 = pos1 / MATRIX_WIDTH;
      uint8_t x2 = pos2 % MATRIX_WIDTH;
      uint8_t y2 = pos2 / MATRIX_WIDTH;

      // Swap cluster IDs
      uint8_t tempID = pixelClusterID[y1][x1];
      pixelClusterID[y1][x1] = pixelClusterID[y2][x2];
      pixelClusterID[y2][x2] = tempID;
    }

    pixelOffset += cluster.pixels;
  }
}
