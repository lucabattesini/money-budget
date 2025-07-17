import React from "react"

export default function ReportExpense() {
    return (
        <div className="container">
            <h1>
                Report Expenses
            </h1>
            <label htmlFor=""></label>
            <input type="number" />

            <label htmlFor=""></label>
            <input type="number" />

            <label htmlFor=""></label>
            <input type="number" />

            <button>Submit</button>
        </div>
    );
}