import { useState, useEffect } from "react"
import { Stack, Center, Heading } from "@chakra-ui/react"
import { getAllCategories, getAllTransactions } from "../api/endpoints";

export default function Dashboard() {
    const [transactions, setTransactions] = useState([]);
    const [categories, setCategories] = useState([]);
    useEffect(() => {
            getAllCategories().then(data => setCategories(data.data))
        }, []);

    useEffect(() => {
            getAllTransactions().then(data => setTransactions(data.data))
        }, []);
    
    return(
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={16}
            >
                <Heading>
                    Dashboard
                </Heading>
            </Stack>
        </Center>
    )
}