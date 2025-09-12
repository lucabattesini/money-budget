import { useState } from "react";
import { Center, Stack, Input, Button, Heading } from "@chakra-ui/react";
import { createUser } from "../api/endpoints";

export default function CreateAccount() {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    const handleSubmit = () => {
        const userInfo = {
            name: name,
            email: email,
            password: password 
        };

        createUser(userInfo)
        .then(data => {
            console.log("Successfully requested", data);
        })
    }

    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading size="2xl">
                    Create account
                </Heading>

                <Input 
                placeholder="User name" variant="outline"
                value={name} onChange={(e) => setName(e.target.value)}
                />

                <Input 
                placeholder="Email address" variant="outline"
                value={email} onChange={(e) => setEmail(e.target.value)}
                />

                <Input 
                placeholder="Password" variant="outline"
                value={password} onChange={(e) => setPassword(e.target.value)}
                />

                <Button onClick={handleSubmit}>
                    Sign In
                </Button>
            </Stack>
        </Center>
    );
}