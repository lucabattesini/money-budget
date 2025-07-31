import React, { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Menu, Portal} from "@chakra-ui/react";

export default function ReportExpense() {
    const [categories, setCategories] = useState([]);

    useEffect(() => {
        fetch("http://127.0.0.1:8000/categories/", {
            method: "get"
        })
            .then(Response => Response.json())
            .then(data => setCategories(data))

            .catch(error => console.error("Failed to search categories", error))
    }, [])

    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="center"
            >
                <Heading>
                    Report Expense
                </Heading>

                <Input type="number" placeholder="Amount" variant="outline" />
                <Input placeholder="Description" variant="outline"/>

                <Menu.Root>
                    <Menu.Trigger asChild>
                        <Button variant="outline">
                            Category
                        </Button>
                    </Menu.Trigger>
                    <Portal>
                        <Menu.Positioner>
                            <Menu.Content>
                                <Menu.Item value="Self-Care">Self-care</Menu.Item>
                                <Menu.Item value="Food">Food</Menu.Item>
                                <Menu.Item value="Hobbies">Hobbies</Menu.Item>
                            </Menu.Content>
                        </Menu.Positioner>
                    </Portal>
                </Menu.Root>
                
                <Button>Submit</Button>
            </Stack>
        </Center>
    );
}   