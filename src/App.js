import React, { useState, useEffect } from 'react';
import './App.css';
import InputField from './InputField.jsx';

function App() {
  const [currentTest, setCurrentTest] = useState('');

  const TriggerReport = () => {
    fetch('/trigger_report').then(res => res.json()).then(data => {
      setCurrentTest(data.reportID);
    })
  }


  return (
    <div className="App">
      <header className="App-header">
        <button className = "triggerButton" onClick = {() => TriggerReport()}>TriggerReport</button>
        <p className = "reportText">Your report id is: {currentTest}</p>
        <InputField/>
      </header>
    </div>
  );
}

export default App;
