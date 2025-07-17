import React, {useState} from "react";

export default function CreateAccount() {

    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault(); // Prevent the autoatic page reload

        const data = {
            name,
            email,
            password
        };

        try {
            const response = await fetch("http://127.0.0.1:8000/create-profile/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();
            console.log(result)
        }   catch (error) {
                console.error("error")
            };
    };

    return (
        <div>
            <form onSubmit={handleSubmit}>
                <div className="container">
                    <h2>
                        Fill the following inputs
                    </h2>

                    <label htmlFor="name">Name</label>
                    <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={e => setName(e.target.value)} // Atualiza o estado quando digita
                    />

                    <label htmlFor="email">Email</label>
                    <input 
                    id="email"
                    type="text"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    />

                    <label htmlFor="password">Password</label>
                    <input id="password"
                    type="text" 
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    />

                    <button type="submit">Submit</button>
                </div>
            </form>
        </div>
    );
}