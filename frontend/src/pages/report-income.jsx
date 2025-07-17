import React from "react"

export default function ReportIncome() {
    return (
        <div className="container">
            <h1>
                Report Incomes
            </h1>
            <label htmlFor="Investment">Investment</label>
            <input type="number" />

            <label htmlFor="Emergency found">Emergency found</label>
            <input type="number" />

            <label htmlFor="Checking account">Checking account</label>
            <input type="number" />

            <button>Submit</button>
        </div>
    );
}