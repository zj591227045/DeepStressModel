# DeepStressModel

English | [简体中文](./README_zh-CN.md)

DeepStressModel is a powerful AI model performance testing and monitoring tool specifically designed for evaluating and analyzing the performance of large language models. Through an intuitive graphical interface and comprehensive data analysis capabilities, it helps developers and researchers better understand and optimize their AI models.

## 🌟 Core Features

### 1. Comprehensive Performance Testing
- **Concurrent Testing**: Support for customizable concurrent stress testing
- **Multi-Dataset Support**: Test multiple datasets simultaneously with weight configuration
- **Real-time Monitoring**: Visual display of key metrics including response time and generation speed
- **Automated Testing**: Support for batch testing and scheduled tasks (in development)
- **Output Modes**: Support for streaming output and direct output testing modes

### 2. GPU Resource Monitoring
- **Multi-GPU Monitoring**: Support for parallel monitoring and load balancing analysis of multiple GPU cards
- **Real-time Tracking**: Monitor local and remote GPU usage in real-time
- **Remote Connection**: Support custom SSH port (default 22) for flexible server configuration
- **Key Metrics**: Track memory usage, GPU utilization, temperature, power consumption and more
- **Historical Records**: Save monitoring data for trend analysis and load prediction

### 3. Model Benchmarking System
- **Standardized Testing Process**: Normalized testing based on preset test sets and fixed test environments
- **Automatic Framework Detection**: Automatically identify the framework type of the running model (such as Ollama, llama.cpp, vLLM, etc.)
- **Multi-dimensional Evaluation**: Comprehensive assessment of model performance across throughput, latency, response time, and more
- **Leaderboard Support**: Support both online and offline modes for submitting test results to the leaderboard
- **Secure Encryption**: Result encryption functionality to protect sensitive test data
- **Automatic Scoring**: Automatic calculation of comprehensive scores based on multi-dimensional performance metrics

### 4. Data Analysis and Visualization
- **Rich Charts**: Multi-dimensional data visualization
- **Performance Metrics**: Including average response time, TPS, generation speed, etc.
- **Data Export**: Support for test data export and report generation

### 5. User-Friendly Interface
- **Intuitive Operation**: Clear tab-based design
- **Real-time Feedback**: Live display of test progress and results
- **Flexible Configuration**: Support for various customizable test parameters

## 🛠️ Technical Architecture

### Core Modules
1. **GUI Module**
   - Built on PyQt5
   - Responsive interface design
   - Multi-tab management
   - Real-time data flow visualization

2. **Testing Engine**
   - Asynchronous concurrent processing
   - API call management
   - Data collection and statistics
   - Support for streaming and direct output modes
   - Intelligent load balancing

3. **Monitoring System**
   - Multi-GPU resource monitoring
   - System performance tracking
   - Remote monitoring support
   - Load balancing analysis
   - Performance warning mechanism

4. **Benchmarking System**
   - Standardized testing protocols
   - Automatic framework recognition
   - Result encryption and verification
   - Local result storage and upload
   - Multi-mode (online/offline) support

5. **Data Management**
   - SQLite data storage
   - Configuration management
   - Test record persistence
   - Encrypted data processing

## 📊 Model Performance Leaderboard

DeepStressModel provides a complete model performance leaderboard system to help users understand the performance of different models in various hardware environments.
Access at: https://tops.ginease.cn:4433

### Leaderboard Features
- **Global Ranking**: View model performance rankings on a global scale
- **Multi-dimensional Sorting**: Sort by throughput, latency, memory efficiency and other dimensions
- **Hardware Filtering**: Filter leaderboard data based on hardware configurations
- **Result Verification**: Anti-cheating system ensures all submitted results are authentic and reliable
- **Personal Records**: Track testing history on personal devices
- **Online/Offline Mode**: Support both real-time online submission and offline batch submission

### Participating in the Leaderboard
1. **Run Standard Tests**: Use DeepStressModel's built-in standard testing process
2. **Submit Results**: Choose to encrypt and upload results to the leaderboard server
3. **View Rankings**: Check the latest rankings and detailed data analysis through the leaderboard website

### Leaderboard Data Security
- Encrypted result transmission
- Hardware fingerprint verification
- Anti-cheating system monitoring
- User anonymity options

## 📈 Future Plans

### Near-term Plans (v1.x)
1. **Feature Enhancement**
   - Add more data visualization options
   - Support more types of AI models
   - Enhance remote monitoring capabilities

2. **Performance Optimization**
   - Improve large-scale testing performance
   - Optimize memory usage
   - Improve data processing efficiency

3. **Leaderboard Expansion**
   - Build comprehensive scoring system
   - Add model efficiency analysis
   - Support more hardware platforms
   - Add community interaction features
   - Optimize leaderboard UI and user experience

### Long-term Plans
1. **Cloud Integration**
   - Support cloud deployment
   - Distributed testing support
   - Multi-user collaboration features

2. **Intelligent Analysis**
   - AI-assisted analysis
   - Automatic optimization suggestions
   - Intelligent report generation

3. **Ecosystem Expansion**
   - Open API interface
   - Third-party plugin support
   - Cross-platform application support

## 🤝 Contribution Guidelines

We welcome community contributions! If you would like to participate in project development, please:

1. Fork this repository
2. Create your feature branch
3. Submit your changes
4. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details

## 👥 Contact Us

- Project Homepage: [GitHub](https://github.com/yourusername/DeepStressModel)
- Issue Reporting: [Issues](https://github.com/yourusername/DeepStressModel/issues)
- Email Contact: your.email@example.com

---

**DeepStressModel** - Making AI model testing simpler and more efficient! 