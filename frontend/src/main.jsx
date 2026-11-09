import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { installErrorLogging, reportError } from './logging.js'
import './styles.css'
import './app-theme.css'

installErrorLogging()

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) { return { error } }
  componentDidCatch(error, info) { reportError(error.message, `${error.stack}\n${info.componentStack}`) }
  render() {
    if (this.state.error) {
      return (
        <div className="fatal">
          <h1>Something went wrong</h1>
          <p>The error was logged to logs/punca.log. Reload the page to continue.</p>
          <button className="btn" onClick={() => window.location.reload()}>Reload</button>
        </div>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(
  <ErrorBoundary><App /></ErrorBoundary>,
)
