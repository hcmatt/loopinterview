import React, { useState } from 'react';
import "./App.css"

const InputField = () => {
    const [inputValue, setInputValue] = useState('');
    const [inputValueDisplay, setInputValueDisplay] = useState('');
    const [status, setStatus] = useState('');

    const handleInputChange = (event) => {
        setInputValue(event.target.value);
    };

    const handleFormSubmit = (event) => {
        event.preventDefault();
        getReportData(inputValue)
    }

    const getReportData = (reportId) => {
        fetch(`/get_report?input=${reportId}`)
            .then(response => response.json())
            .then(data => {
            const statusCheck = data.status;
            if (statusCheck === 'Running') {
                setStatus('Running')
            } else if (statusCheck === 'Complete') {
                setStatus('Complete')
            } else {
                setStatus('error')
            }
        })
        .catch(error => {
            setStatus(error)
        });
    };

    const handleDownloadClick = () => {
        fetch('/download_report')
            .then((response) => response.blob())
            .then((blob) => {
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = 'report.csv';
                link.click();
                URL.revokeObjectURL(url);
            })
            .catch((error) => {
                console.error('Error:', error);
            });
    };


    return (
        <div>
            <form onSubmit = {handleFormSubmit}>
                <input placeHolder = "reportID" className = "inputClass" type = "text" value = {inputValue} onChange = {handleInputChange} />
                <button className = "buttonClass" type = "submit">Submit</button>
                <div className = "statusClass">{status}</div>
            </form>
            {status === 'Complete' && (<button className = "downloadButton" onClick = {() => handleDownloadClick()}>DownloadReport</button>)}
        </div>
    )
};

export default InputField;